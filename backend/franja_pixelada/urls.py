"""
Franja Pixelada — URL Configuration
"""
from django.contrib.auth import logout as auth_logout
from django.http import HttpResponseRedirect
from django.urls import path, include, re_path
from django.conf import settings
from django.views.generic import TemplateView
from core.admin_site import admin_site   # AdminSite con MFA (OTP) obligatorio
from core.views import health_live, serve_media_debug
from orders.file_views import staff_order_payment_proof


def admin_logout_get(request):
    """
    Acepta GET en logout para compatibilidad con Jazzmin en Django 5.
    Django 5 cambió logout a solo-POST; Jazzmin sigue enviando GET.
    """
    auth_logout(request)
    return HttpResponseRedirect(f'/{settings.ADMIN_URL}')


class SPAView(TemplateView):
    """SPA principal — expone admin_url solo a usuarios staff autenticados."""
    template_name = 'store/index.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated and self.request.user.is_staff:
            ctx['admin_url'] = f'/{settings.ADMIN_URL}'
        return ctx


urlpatterns = [
    path('health/', health_live, name='health_live'),
    # ── Frontend SPA ───────────────────────────────────
    path('', SPAView.as_view(), name='home'),

    # ── Admin con MFA TOTP ──────────────────────────────
    # La URL se configura mediante ADMIN_URL en .env (por defecto 'admin/')
    # Override de logout para compatibilidad Jazzmin + Django 5 (GET → POST)
    path(f'{settings.ADMIN_URL}logout/', admin_logout_get),
    path(settings.ADMIN_URL, admin_site.urls),

    # ── Archivos sensibles (sesión staff del admin, no JWT) ───────────────────
    path(
        'internal/staff/orders/<uuid:order_id>/payment-proof/',
        staff_order_payment_proof,
        name='staff_order_payment_proof',
    ),

    # ── API v1 ──────────────────────────────────────────
    path('api/v1/auth/', include('users.urls')),
    path('api/v1/products/', include('products.urls')),
    path('api/v1/orders/', include('orders.urls')),
    path('api/v1/payments/', include('payments.urls')),
    path('api/v1/proveedores/', include('proveedores.urls')),
    path('api/v1/loyalty/', include('loyalty.urls')),
    path('api/v1/core/', include('core.urls')),
    path('api/v1/returns/', include('returns.urls')),
]

if settings.DEBUG:
    # No usar static(MEDIA_URL) completo: expondría ``protected/`` igual que en prod bloquea Nginx.
    prefix = settings.MEDIA_URL.lstrip('/')
    urlpatterns += [
        re_path(r'^' + prefix + r'(?P<path>.*)$', serve_media_debug),
    ]
