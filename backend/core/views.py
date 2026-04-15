"""
Franja Pixelada — Vistas internas de core
"""
import json
import logging
import posixpath
import urllib.request

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404, JsonResponse
from django.utils.timezone import now
from django.views.decorators.http import require_http_methods
from django.views.static import serve

logger = logging.getLogger(__name__)

_RATE_API = 'https://open.er-api.com/v6/latest/USD'


@require_http_methods(["GET", "HEAD"])
def health_live(request):
    """Señal liviana para healthcheck (Docker / balanceadores / tests). Sin consultas a BD."""
    return JsonResponse({
        'status': 'ok',
        'service': 'franja_pixelada',
        'timestamp': now().isoformat(),
    })


# Prefijos de MEDIA_ROOT que no deben servirse por URL directa (misma política que nginx).
_FORBIDDEN_MEDIA_PREFIXES = (
    'protected/',
    'payment_proofs/',
    'profile_images/',
)


@require_http_methods(["GET", "HEAD"])
def serve_media_debug(request, path):
    """
    En DEBUG sustituye el ``static(MEDIA_URL)`` genérico: evita filtrar avatares,
    comprobantes u otros uploads acotados que en producción bloquea Nginx.
    """
    norm = posixpath.normpath(path.replace('\\', '/'))
    if norm.startswith('../') or '/../' in norm or norm == '..':
        raise Http404()
    low = norm.lower()
    for prefix in _FORBIDDEN_MEDIA_PREFIXES:
        if low.startswith(prefix):
            raise Http404()
    return serve(request, path, document_root=settings.MEDIA_ROOT)


@staff_member_required
def exchange_rate_live(request):
    """
    Consulta la tasa USD → COP desde una API pública gratuita.
    Solo accesible para staff (admin).
    """
    try:
        with urllib.request.urlopen(_RATE_API, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        cop = data['rates'].get('COP')
        if not cop:
            return JsonResponse({'error': 'COP no encontrado en la respuesta'}, status=502)
        return JsonResponse({
            'rate': round(float(cop), 2),
            'source': 'open.er-api.com',
            'time_last_update': data.get('time_last_update_utc', ''),
        })
    except Exception as e:
        logger.warning('Error consultando tasa de cambio: %s', e, exc_info=True)
        return JsonResponse(
            {'error': 'No se pudo obtener la tasa de cambio.'},
            status=502,
        )
