"""
Proveedores — URLs

Endpoints públicos (sin JWT):
  POST /api/v1/proveedores/webhooks/<slug>/   → recibe webhooks de proveedores

Endpoints internos (requieren IsAdminUser):
  GET  /api/v1/proveedores/estado/            → estado de todos los proveedores
  GET  /api/v1/proveedores/<slug>/logs/       → últimos 100 logs de un proveedor
"""
from django.urls import path
from .views import (
    WebhookProveedorView, EstadoProveedoresView, LogsProveedorView,
    CatalogoProveedorView,
    ProductoVinculadoView, ProductoVinculadoDetalleView, RecalcularVinculoView,
)

app_name = 'proveedores'

urlpatterns = [
    # ── Webhook público ──────────────────────────────────────────────────────
    # POST — recibe eventos del proveedor (sin JWT, validación HMAC)
    path('webhooks/<slug:proveedor_slug>/', WebhookProveedorView.as_view(), name='webhook'),

    # ── Monitoreo interno (solo admin) ───────────────────────────────────────
    path('estado/',                         EstadoProveedoresView.as_view(),  name='estado'),
    path('<slug:proveedor_slug>/logs/',     LogsProveedorView.as_view(),      name='logs'),

    # ── Catálogo del proveedor ───────────────────────────────────────────────
    # GET  — lista variantes sincronizadas disponibles para vincular
    path('<slug:proveedor_slug>/catalogo/', CatalogoProveedorView.as_view(),  name='catalogo'),

    # ── Vínculos (capped stock sync) ─────────────────────────────────────────
    # GET  — lista todos los vínculos activos con stock calculado
    # POST — crea un nuevo vínculo variante-proveedor ↔ producto-catálogo
    path('vinculados/',                     ProductoVinculadoView.as_view(),        name='vinculados'),
    # GET   — detalle de un vínculo
    # PATCH — editar stock_maximo, activo, sincronizar
    # DELETE — eliminar vínculo
    path('vinculados/<uuid:pk>/',           ProductoVinculadoDetalleView.as_view(), name='vinculado-detalle'),
    # POST — forzar recálculo inmediato del stock
    path('vinculados/<uuid:pk>/recalcular/', RecalcularVinculoView.as_view(),       name='recalcular'),
]
