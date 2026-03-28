"""
Franja Pixelada — Panel de administración con MFA obligatorio

Extiende OTPAdminSite de django-otp para requerir verificación TOTP
(Google Authenticator, Authy, etc.) además del usuario + contraseña.

Flujo de configuración para un nuevo admin:
1. El superusuario inicia sesión normalmente (user + password).
2. En el panel ve el aviso "Dispositivo OTP no configurado".
3. Va a Administración > TOTP Devices > Agregar y escanea el QR.
4. A partir del siguiente login deberá ingresar el código de 6 dígitos.
5. Los códigos estáticos de respaldo se generan en "Static Devices".

Para deshabilitar OTP en desarrollo: DISABLE_ADMIN_OTP=True en .env
"""
from django.conf import settings

if getattr(settings, 'DISABLE_ADMIN_OTP', False):
    from django.contrib.admin import AdminSite as _BaseAdminSite
else:
    from django_otp.admin import OTPAdminSite as _BaseAdminSite


class FranjaAdminSite(_BaseAdminSite):
    """
    AdminSite que hereda OTPAdminSite (MFA activo) o AdminSite estándar
    según la variable DISABLE_ADMIN_OTP en settings.

    Con OTP activo (producción):
    - Requiere que request.user.is_verified() == True para acceder.
    - Redirige a la pantalla de verificación OTP si el token no fue ingresado.
    - Los superusuarios sin dispositivo configurado ven un aviso pero
      pueden acceder (para poder configurar su primer dispositivo).

    Sin OTP (desarrollo: DISABLE_ADMIN_OTP=True):
    - Solo requiere usuario + contraseña.
    """
    site_header = 'Franja Pixelada — Administración'
    site_title  = 'Franja Pixelada Admin'
    index_title = 'Panel de Control'

    def each_context(self, request):
        """Inyecta métricas de negocio en el contexto de todas las páginas admin."""
        ctx = super().each_context(request)
        if not request.user.is_authenticated:
            return ctx
        try:
            from django.utils import timezone
            from django.db.models import Sum, F
            from orders.models import Order
            from products.models import Product

            today          = timezone.localdate()
            first_of_month = today.replace(day=1)

            ingresos = (
                Order.objects
                .filter(created_at__date__gte=first_of_month, payment_status='paid')
                .aggregate(t=Sum('total'))['t'] or 0
            )

            ctx.update({
                'kpi_ordenes_hoy':       Order.objects.filter(
                                             created_at__date=today).count(),
                'kpi_ordenes_mes':       Order.objects.filter(
                                             created_at__date__gte=first_of_month).count(),
                'kpi_ingresos_mes_str':  '$ {:,.0f}'.format(int(ingresos)).replace(',', '.'),
                'kpi_productos_activos': Product.objects.filter(status='active').count(),
                'kpi_stock_bajo':        Product.objects.filter(
                                             status='active', stock__gt=0,
                                             stock__lte=F('low_stock_threshold'),
                                         ).count(),
                'kpi_sin_stock':         Product.objects.filter(
                                             status='active', stock=0).count(),
            })
        except Exception:
            pass  # nunca romper el admin por una métrica fallida
        return ctx


# Instancia global que reemplaza al admin.site por defecto en urls.py
admin_site = FranjaAdminSite(name='admin')
