from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import get_user_model
from django.conf import settings
from .serializers import UserSerializer, RegisterSerializer, CustomTokenObtainPairSerializer

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
            'user': UserSerializer(user).data,
            'access': str(refresh.access_token),
            # refresh NO se incluye en el body — viaja como HttpOnly cookie
        }, status=status.HTTP_201_CREATED)
        _set_refresh_cookie(response, str(refresh))
        return response


class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

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
    permission_classes = [IsAuthenticated]

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
