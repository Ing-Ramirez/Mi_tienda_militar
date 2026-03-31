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
from django.http import FileResponse
from django.shortcuts import get_object_or_404
import mimetypes

from products.validators import validate_image_file
from .serializers import (
    UserSerializer,
    RegisterSerializer,
    CustomTokenObtainPairSerializer,
    AuthUserBriefSerializer,
)
from .throttles import LoginRateThrottle, AvatarMediaAnonThrottle
from .media_tokens import parse_avatar_media_token, signed_avatar_absolute_url

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
    """Elimina la cookie del refresh token."""
    response.delete_cookie(
        key=_COOKIE_NAME,
        path=_COOKIE_PATH,
        httponly=True,
        secure=not settings.DEBUG,
        samesite='Lax',
    )


# ── Views ─────────────────────────────────────────────────────────────────────

class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

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


class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [LoginRateThrottle]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            # Extraer refresh del body y moverlo a cookie HttpOnly
            refresh_token = response.data.pop('refresh', None)
            if refresh_token:
                _set_refresh_cookie(response, refresh_token)
        return response


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
        except Exception:
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
            except Exception:
                pass
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
