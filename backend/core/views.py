"""
Franja Pixelada — Vistas internas de core
"""
import urllib.request
import json
import logging

from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse

logger = logging.getLogger(__name__)

_RATE_API = 'https://open.er-api.com/v6/latest/USD'


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
        logger.warning('Error consultando tasa de cambio: %s', e)
        return JsonResponse({'error': str(e)}, status=502)
