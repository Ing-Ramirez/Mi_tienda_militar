"""Throttling para endpoints sensibles de pedidos."""
from rest_framework.throttling import AnonRateThrottle


class PaymentProofMediaAnonThrottle(AnonRateThrottle):
    """Limita descargas del comprobante por URL firmada."""
    rate = '120/hour'
