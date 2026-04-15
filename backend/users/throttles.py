from rest_framework.throttling import AnonRateThrottle


class AvatarMediaAnonThrottle(AnonRateThrottle):
    """Limita descargas anónimas del avatar vía URL firmada."""
    rate = '400/hour'


class LoginRateThrottle(AnonRateThrottle):
    """
    Aplica throttling por IP al endpoint de login.

    El valor se toma desde REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['login'].
    """

    scope = 'login'


class RegisterRateThrottle(AnonRateThrottle):
    """Limita creación masiva de cuentas por IP (OWASP: abuso / enumeración)."""

    scope = 'register'

