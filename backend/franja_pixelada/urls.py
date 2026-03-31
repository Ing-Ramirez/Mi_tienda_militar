"""
Franja Pixelada — URL Configuration
"""
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from core.admin_site import admin_site   # AdminSite con MFA (OTP) obligatorio
from orders.file_views import staff_order_payment_proof

urlpatterns = [
    # ── Frontend SPA ───────────────────────────────────
    path('', TemplateView.as_view(
        template_name='store/index.html',
        extra_context={'admin_url': f'/{settings.ADMIN_URL}'},
    ), name='home'),

    # ── Admin con MFA TOTP ──────────────────────────────
    # La URL se configura mediante ADMIN_URL en .env (por defecto 'admin/')
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
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
