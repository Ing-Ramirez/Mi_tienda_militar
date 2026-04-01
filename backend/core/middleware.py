"""
Franja Pixelada — Middleware de seguridad

1. SecurityHeadersMiddleware    — CSP con nonce, HSTS, Permissions-Policy, etc.
2. AdminBruteForceMiddleware    — bloquea IPs/usuarios con demasiados fallos
3. AdminSessionTimeoutMiddleware — cierra sesión tras 30 min de inactividad
"""
import base64
import os
import time
import logging
import re
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import logout
from django.http import HttpResponse
from django.shortcuts import redirect
from django.utils import timezone


# ── 1. SecurityHeadersMiddleware ──────────────────────────────────────────────

def csp_nonce_context(request):
    """Context processor: expone el nonce CSP a las plantillas Django."""
    return {'csp_nonce': getattr(request, 'csp_nonce', '')}


class SecurityHeadersMiddleware:
    """
    Agrega cabeceras de seguridad HTTP a todas las respuestas y gestiona
    el nonce CSP por request para permitir el bloque <script> y <style>
    inline de index.html sin necesitar 'unsafe-inline'.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Generar nonce único por request (16 bytes → 22 caracteres base64url)
        request.csp_nonce = base64.urlsafe_b64encode(os.urandom(16)).rstrip(b'=').decode()

        response = self.get_response(request)

        admin_url = getattr(settings, 'ADMIN_URL', 'admin/')
        is_admin = request.path.startswith(f'/{admin_url}')
        self._add_security_headers(response, request.csp_nonce, is_admin=is_admin)
        return response

    def _build_csp(self, nonce: str, is_admin: bool = False) -> str:
        """
        Construye la política CSP.

        Admin: usa 'unsafe-inline' para scripts y estilos porque los templates
        de Django admin contienen inline <script>/<style> que no pueden recibir
        nonce (son plantillas de Django, no de Jinja2 con contexto inyectado).
        'frame-ancestors self' permite que el popup de FK (window.open) comunique
        con la ventana padre mediante window.opener.

        Frontend público: nonce estricto, frame-ancestors 'none'.
        """
        if is_admin:
            directives = [
                "default-src 'self'",
                "script-src 'self' 'unsafe-inline'",
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
                "font-src 'self' https://fonts.gstatic.com data:",
                "img-src 'self' data: blob:",
                "connect-src 'self' https://open.er-api.com",
                "frame-src 'self'",
                "object-src 'none'",
                "base-uri 'self'",
                "form-action 'self'",
                # 'self' permite que el popup se abra y comunique con la ventana padre
                "frame-ancestors 'self'",
            ]
        else:
            directives = [
                "default-src 'self'",

                # Scripts: solo mismo origen con nonce válido.
                f"script-src 'self' 'nonce-{nonce}'",

                # Estilos: mismo origen + nonce para el bloque <style> inline + Google Fonts CSS
                f"style-src 'self' 'nonce-{nonce}' https://fonts.googleapis.com",

                # Fuentes tipográficas
                "font-src 'self' https://fonts.gstatic.com",

                # Imágenes: mismo origen + data URIs + blobs + thumbnails de YouTube/Vimeo
                "img-src 'self' data: blob: https://i.ytimg.com https://i.vimeocdn.com",

                # Conexiones fetch/XHR
                "connect-src 'self'",

                # Frames: YouTube/Vimeo para video hero + 3DS de Stripe
                "frame-src https://www.youtube.com https://www.youtube-nocookie.com https://player.vimeo.com",

                # Sin plugins Flash ni objetos embebidos
                "object-src 'none'",

                # Protege contra inyección de etiqueta <base>
                "base-uri 'self'",

                # Los formularios solo pueden hacer POST al mismo origen
                "form-action 'self'",

                # No permitir ser embebido en iframes externos
                "frame-ancestors 'none'",
            ]

        if not settings.DEBUG:
            directives.append("upgrade-insecure-requests")

        return "; ".join(directives)

    def _add_security_headers(self, response, nonce: str, is_admin: bool = False) -> None:
        response['Content-Security-Policy'] = self._build_csp(nonce, is_admin=is_admin)

        # Evitar que el navegador infiera tipo MIME (ya configurado en Django settings
        # pero lo duplicamos aquí para que aplique en todas las respuestas)
        response['X-Content-Type-Options'] = 'nosniff'

        # Control granular de permisos de hardware/APIs del navegador
        response['Permissions-Policy'] = (
            'geolocation=(), '
            'microphone=(), '
            'camera=(), '
            'payment=(self), '       # Permitir Payment Request API solo en mismo origen
            'usb=(), '
            'magnetometer=(), '
            'accelerometer=()'
        )

        # Referrer estricto (ya configurado en Django settings, refuerzo aquí)
        response.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')

logger = logging.getLogger('core.security')
security_events_logger = logging.getLogger('security.events')

ADMIN_URL = getattr(settings, 'ADMIN_URL', 'panel-fp-admin/')
LOCKOUT_SOFT_ATTEMPTS = 5        # Intentos antes de bloqueo corto
LOCKOUT_HARD_ATTEMPTS = 10       # Intentos antes de bloqueo largo
LOCKOUT_SOFT_MINUTES = 15        # Minutos de bloqueo corto
LOCKOUT_HARD_MINUTES = 60        # Minutos de bloqueo largo
ADMIN_SESSION_TIMEOUT = 30 * 60  # 30 minutos de inactividad


def _get_client_ip(request) -> str:
    """
    Extrae la IP real del cliente usando django-ipware.

    - Respeta IPWARE_META_PRECEDENCE_ORDER y IPWARE_TRUSTED_PROXY_COUNT
      definidos en settings.py.
    - Un atacante no puede inyectar una IP falsa via X-Forwarded-For porque
      ipware descarta los saltos de proxy no confiables.
    - Retorna '0.0.0.0' solo si no es posible determinar la IP (caso raro).
    """
    try:
        from ipware import get_client_ip
        ip, is_routable = get_client_ip(request)
        if ip:
            return ip
    except ImportError:
        logger.warning('django-ipware no está instalado — usando REMOTE_ADDR sin validación')
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


def _send_security_alert(subject, body):
    """Envía email de alerta al administrador principal."""
    alert_email = getattr(settings, 'ADMIN_SECURITY_EMAIL', None)
    if not alert_email:
        return
    try:
        from django.core.mail import send_mail
        send_mail(
            subject=f'[Franja Pixelada] {subject}',
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[alert_email],
            fail_silently=True,
        )
    except Exception as e:
        logger.error(f'Error enviando alerta de seguridad: {e}')


class AdminBruteForceMiddleware:
    """
    Protege el login del admin contra ataques de fuerza bruta.
    - 5 fallos en 1h → bloqueo de 15 min
    - 10 fallos en 1h → bloqueo de 1h
    Registra todos los intentos en LoginAttempt.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        admin_login_path = f'/{ADMIN_URL}login/'

        # Antes de procesar el POST de login, verificar bloqueo
        if request.path == admin_login_path and request.method == 'POST':
            raw_username = request.POST.get('username', '').strip()
            username = raw_username or '__anonymous__'
            ip = _get_client_ip(request)

            block_response = self._check_lockout(username, ip)
            if block_response:
                return block_response

        response = self.get_response(request)

        # Después de procesar el login, registrar el intento
        if request.path == admin_login_path and request.method == 'POST':
            raw_username = request.POST.get('username', '').strip()
            username = raw_username or '__anonymous__'
            ip = _get_client_ip(request)
            # Éxito = redirige (302) al panel; fallo = renderiza login de nuevo (200)
            was_successful = response.status_code in (301, 302)
            self._record_attempt(request, username, ip, was_successful)

        return response

    def _check_lockout(self, username, ip):
        try:
            from .models import LoginAttempt
            one_hour_ago = timezone.now() - timedelta(hours=1)

            recent = LoginAttempt.objects.filter(
                username=username,
                was_successful=False,
                timestamp__gte=one_hour_ago,
            ).order_by('-timestamp')

            count = recent.count()

            if count >= LOCKOUT_HARD_ATTEMPTS:
                last = recent.first()
                elapsed = (timezone.now() - last.timestamp).total_seconds() / 60
                if elapsed < LOCKOUT_HARD_MINUTES:
                    remaining = int(LOCKOUT_HARD_MINUTES - elapsed)
                    logger.warning(f'BLOQUEO DURO: {username} desde {ip}')
                    return HttpResponse(
                        f'Acceso bloqueado por demasiados intentos fallidos. '
                        f'Intente nuevamente en {remaining} minutos.',
                        status=429,
                        content_type='text/plain; charset=utf-8',
                    )

            elif count >= LOCKOUT_SOFT_ATTEMPTS:
                last = recent.first()
                elapsed = (timezone.now() - last.timestamp).total_seconds() / 60
                if elapsed < LOCKOUT_SOFT_MINUTES:
                    remaining = int(LOCKOUT_SOFT_MINUTES - elapsed)
                    logger.warning(f'BLOQUEO SUAVE: {username} desde {ip}')
                    return HttpResponse(
                        f'Demasiados intentos fallidos. '
                        f'Intente nuevamente en {remaining} minutos.',
                        status=429,
                        content_type='text/plain; charset=utf-8',
                    )
        except Exception as e:
            logger.error(f'Error verificando bloqueo: {e}')
        return None

    def _record_attempt(self, request, username, ip, was_successful):
        try:
            from .models import LoginAttempt
            attempt = LoginAttempt.objects.create(
                username=username,
                ip_address=ip,
                was_successful=was_successful,
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
            )
            logger.info(
                f'Login {"OK" if was_successful else "FALLO"}: '
                f'{username} desde {ip}'
            )
            # Alertas automáticas
            if not was_successful:
                one_hour_ago = timezone.now() - timedelta(hours=1)
                failures = LoginAttempt.objects.filter(
                    username=username,
                    was_successful=False,
                    timestamp__gte=one_hour_ago,
                ).count()
                if failures in (LOCKOUT_SOFT_ATTEMPTS, LOCKOUT_HARD_ATTEMPTS):
                    _send_security_alert(
                        f'Alerta: {failures} intentos fallidos — {username}',
                        f'Se detectaron {failures} intentos de login fallidos.\n'
                        f'Usuario: {username}\n'
                        f'IP: {ip}\n'
                        f'Hora: {timezone.now():%d/%m/%Y %H:%M:%S}\n'
                    )
        except Exception as e:
            logger.error(f'Error registrando intento de login: {e}')


class AdminSessionTimeoutMiddleware:
    """
    Cierra la sesión del administrador después de ADMIN_SESSION_TIMEOUT
    segundos de inactividad en el panel.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.path.startswith(f'/{ADMIN_URL}')
            and not request.path == f'/{ADMIN_URL}login/'
            and request.user.is_authenticated
            and (request.user.is_staff or request.user.is_superuser)
        ):
            last_activity = request.session.get('admin_last_activity')
            now = time.time()

            if last_activity is not None:
                idle_seconds = now - last_activity
                if idle_seconds > ADMIN_SESSION_TIMEOUT:
                    logout(request)
                    login_url = f'/{ADMIN_URL}login/?next={request.path}&timeout=1'
                    logger.info(
                        f'Sesión admin expirada por inactividad: '
                        f'{request.user} ({idle_seconds:.0f}s sin actividad)'
                    )
                    return redirect(login_url)

            request.session['admin_last_activity'] = now

        return self.get_response(request)


class SecurityMonitoringMiddleware:
    """
    Telemetría defensiva para SIEM:
    - Asigna/propaga X-Request-ID.
    - Reporta señales de probing/inyección para correlación.
    - Registra respuestas de abuso (401/403/405/429) en rutas críticas.
    """

    _SUSPICIOUS_RE = re.compile(
        r"(<script|%3cscript|union(?:\+|%20)select|sleep\(|benchmark\(|\.\./|or(?:\+|%20)1=1)",
        re.IGNORECASE,
    )
    _CRITICAL_PREFIXES = (
        "/api/v1/auth/",
        "/api/v1/orders/",
        "/api/v1/payments/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.META.get("HTTP_X_REQUEST_ID") or str(uuid.uuid4())
        request.request_id = request_id
        request.META["HTTP_X_REQUEST_ID"] = request_id

        response = self.get_response(request)
        response.setdefault("X-Request-ID", request_id)

        ip = _get_client_ip(request)
        path = request.path or ""
        qs = request.META.get("QUERY_STRING", "")
        ua = (request.META.get("HTTP_USER_AGENT", "") or "")[:300]
        status_code = int(getattr(response, "status_code", 0) or 0)

        suspicious_input = bool(self._SUSPICIOUS_RE.search(path) or self._SUSPICIOUS_RE.search(qs))
        critical_path = path.startswith(self._CRITICAL_PREFIXES)
        abuse_status = status_code in (401, 403, 405, 429)

        if suspicious_input or (critical_path and abuse_status):
            security_events_logger.warning(
                "SECURITY_EVENT path=%s status=%s ip=%s method=%s request_id=%s ua=%s qs=%s",
                path,
                status_code,
                ip,
                request.method,
                request_id,
                ua,
                qs[:500],
            )

        return response
