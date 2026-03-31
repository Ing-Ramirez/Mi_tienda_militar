"""Límites de tasa específicos para integración con proveedores."""
from rest_framework.throttling import AnonRateThrottle


class WebhookAnonThrottle(AnonRateThrottle):
    """Evita inundar el endpoint público de webhooks (Celery + logs)."""
    rate = '60/minute'
