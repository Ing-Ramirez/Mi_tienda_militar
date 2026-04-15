from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core import signing
from django.core.cache import cache
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404
import logging
import mimetypes
import random
import uuid
import xml.sax.saxutils as xml_esc

from products.validators import validate_image_file
from .serializers import (
    UserSerializer,
    RegisterSerializer,
    CustomTokenObtainPairSerializer,
    AuthUserBriefSerializer,
)
from .throttles import LoginRateThrottle, RegisterRateThrottle, AvatarMediaAnonThrottle
from .media_tokens import parse_avatar_media_token, signed_avatar_absolute_url

logger = logging.getLogger(__name__)

User = get_user_model()

# ── Configuración de la cookie del refresh token ──────────────────────────────
_COOKIE_NAME = 'refresh_token'
_COOKIE_MAX_AGE = 60 * 60 * 24 * 7   # 7 días (igual que REFRESH_TOKEN_LIFETIME)
_COOKIE_PATH = '/api/v1/auth/'        # Restringir al prefijo de auth


def _set_refresh_cookie(response, refresh_token: str) -> None:
    """Establece el refresh token como cookie HttpOnly."""
    response.set_cookie(
        key=_COOKIE_NAME,
        value=refresh_token,
        max_age=_COOKIE_MAX_AGE,
        httponly=True,                          # No accesible desde JS
        secure=not settings.DEBUG,              # Solo HTTPS en producción
        samesite='Lax',                         # Protección CSRF básica
        path=_COOKIE_PATH,
    )


def _clear_refresh_cookie(response) -> None:
    """Elimina la cookie del refresh token.
    Django 5.0.4: delete_cookie() solo acepta key, path, domain, samesite.
    httponly/secure no son necesarios al borrar — el navegador expira la cookie
    independientemente de esos atributos.
    """
    response.delete_cookie(
        key=_COOKIE_NAME,
        path=_COOKIE_PATH,
        samesite='Lax',
    )


# ── Views ─────────────────────────────────────────────────────────────────────

class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    throttle_classes = [RegisterRateThrottle]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        response = Response({
            'user': AuthUserBriefSerializer(user, context={'request': request}).data,
            'access': str(refresh.access_token),
            # refresh NO se incluye en el body — viaja como HttpOnly cookie
        }, status=status.HTTP_201_CREATED)
        _set_refresh_cookie(response, str(refresh))
        return response


class CaptchaView(APIView):
    """
    GET  /api/v1/auth/captcha/
    Genera un código en caché (TTL corto) y devuelve solo el token firmado.
    El cliente debe mostrar el desafío vía GET /captcha/svg/ (no exponer el código en JSON).
    """
    permission_classes = [AllowAny]
    TTL = 20  # segundos
    _CHARS = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'  # sin O/0/I/1

    @classmethod
    def _generate_code(cls, length: int = 6) -> str:
        return ''.join(random.choices(cls._CHARS, k=length))

    def get(self, request):
        code  = self._generate_code()
        nonce = uuid.uuid4().hex
        cache.set(f'captcha:{nonce}', code, timeout=self.TTL)
        token = signing.dumps({'n': nonce}, salt='fp_captcha')
        return Response({
            'captcha_token': token,
            'expires_in':    self.TTL,
        })


class CaptchaSvgView(APIView):
    """
    GET /api/v1/auth/captcha/svg/?captcha_token=...
    Devuelve un SVG con el código (mismo token que /captcha/); evita filtrar el plaintext en JSON.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        token = request.query_params.get('captcha_token', '')
        if not token:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        try:
            data = signing.loads(token, salt='fp_captcha', max_age=CaptchaView.TTL + 2)
        except signing.SignatureExpired:
            return Response(status=status.HTTP_404_NOT_FOUND)
        except signing.BadSignature:
            return Response(status=status.HTTP_403_FORBIDDEN)
        nonce = data.get('n', '')
        code = cache.get(f'captcha:{nonce}')
        if code is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        safe = xml_esc.escape(code)
        svg = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="220" height="56" viewBox="0 0 220 56">'
            f'<rect width="100%" height="100%" fill="#1e293b"/>'
            f'<text x="110" y="36" font-family="monospace,sans-serif" font-size="28" font-weight="bold" '
            f'text-anchor="middle" fill="#e2e8f0" letter-spacing="0.15em">{safe}</text>'
            f'</svg>'
        )
        resp = HttpResponse(svg, content_type='image/svg+xml; charset=utf-8')
        resp['Cache-Control'] = 'private, no-store'
        return resp


class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [LoginRateThrottle]

    def post(self, request, *args, **kwargs):
        if not settings.DISABLE_CAPTCHA:
            token = request.data.get('captcha_token', '')
            code  = (request.data.get('captcha', '') or '').strip().upper()
            error = self._validate_captcha(token, code)
            if error:
                return Response({'captcha': error}, status=status.HTTP_400_BAD_REQUEST)
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            refresh_token = response.data.pop('refresh', None)
            if refresh_token:
                _set_refresh_cookie(response, refresh_token)
        return response

    @staticmethod
    def _validate_captcha(token: str, code: str):
        if not token:
            return 'Código de verificación requerido.'
        try:
            data = signing.loads(token, salt='fp_captcha', max_age=CaptchaView.TTL + 2)
        except signing.SignatureExpired:
            return 'El código expiró. Genera uno nuevo.'
        except signing.BadSignature:
            return 'Token inválido.'
        nonce  = data.get('n', '')
        stored = cache.get(f'captcha:{nonce}')
        if stored is None:
            return 'El código expiró. Genera uno nuevo.'
        cache.delete(f'captcha:{nonce}')   # uso único
        if stored != code:
            return 'Código incorrecto.'
        return None


class CookieTokenRefreshView(APIView):
    """
    Emite un nuevo access token leyendo el refresh token desde la HttpOnly cookie.
    Reemplaza al endpoint estándar /token/refresh/ que requería el token en el body.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.COOKIES.get(_COOKIE_NAME)
        if not refresh_token:
            return Response(
                {'detail': 'No hay sesión activa.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        try:
            token = RefreshToken(refresh_token)
            response = Response({'access': str(token.access_token)})
            # Rotar la cookie si ROTATE_REFRESH_TOKENS = True
            if getattr(settings, 'SIMPLE_JWT', {}).get('ROTATE_REFRESH_TOKENS', False):
                _set_refresh_cookie(response, str(token))
            return response
        except Exception as e:
            logger.warning(
                'cookie_token_refresh_failed',
                extra={'exc_type': type(e).__name__},
            )
            response = Response(
                {'detail': 'Sesión expirada. Inicia sesión nuevamente.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
            _clear_refresh_cookie(response)
            return response


class LogoutView(APIView):
    # Permite cerrar sesión aunque el `access` haya expirado.
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.COOKIES.get(_COOKIE_NAME)
        if refresh_token:
            try:
                RefreshToken(refresh_token).blacklist()
            except Exception as e:
                logger.warning(
                    'logout_refresh_blacklist_failed',
                    extra={'exc_type': type(e).__name__},
                )
        response = Response({'detail': 'Sesión cerrada correctamente.'})
        _clear_refresh_cookie(response)
        return response


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class AvatarUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    _MAX_SIZE = 2 * 1024 * 1024  # 2 MB
    _ALLOWED = {'image/jpeg', 'image/png', 'image/webp'}

    def post(self, request):
        avatar = request.FILES.get('avatar')
        if not avatar:
            return Response({'detail': 'No se envió ningún archivo.'}, status=status.HTTP_400_BAD_REQUEST)
        if avatar.content_type not in self._ALLOWED:
            return Response({'detail': 'Formato no permitido. Usa JPG, PNG o WebP.'}, status=status.HTTP_400_BAD_REQUEST)
        if avatar.size > self._MAX_SIZE:
            return Response({'detail': 'La imagen no puede superar 2 MB.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            # Validación robusta (magic bytes + extensión permitida + tamaño).
            validate_image_file(avatar)
        except DjangoValidationError:
            return Response(
                {'detail': 'Formato no permitido. Sube una imagen JPG, PNG o WebP válida.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = request.user
        if user.profile_image:
            user.profile_image.delete(save=False)
        user.profile_image = avatar
        user.save(update_fields=['profile_image'])
        return Response({'profile_image': signed_avatar_absolute_url(request, user)})


class AvatarMediaView(APIView):
    """Sirve el avatar con token firmado (para etiquetas <img> sin Bearer)."""
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [AvatarMediaAnonThrottle]

    def get(self, request):
        token = request.query_params.get('t')
        if not token:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        try:
            data = parse_avatar_media_token(token)
        except signing.SignatureExpired:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        except signing.BadSignature:
            return Response(status=status.HTTP_403_FORBIDDEN)
        user = get_object_or_404(User, pk=data['u'])
        if not user.profile_image or user.profile_image.name != data['f']:
            return Response(status=status.HTTP_403_FORBIDDEN)
        try:
            fp = user.profile_image.open('rb')
        except FileNotFoundError:
            return Response(status=status.HTTP_404_NOT_FOUND)
        mime, _ = mimetypes.guess_type(user.profile_image.name)
        resp = FileResponse(fp, content_type=mime or 'application/octet-stream')
        resp['Cache-Control'] = 'private, no-store'
        return resp
