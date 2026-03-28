"""
Proveedores — Modelos

Tablas:
  Supplier          → datos de conexión y política de precios (credenciales cifradas)
  SupplierProduct   → catálogo recibido del proveedor (normalizado)
  SupplierVariant   → variantes con stock y precio calculado
  LinkedProduct     → vínculo variante-proveedor ↔ producto-local con max_stock (capped sync)
  SupplierOrder     → pedidos enviados al proveedor
  SupplierTracking  → historial de envío por pedido
  SupplierLog       → auditoría completa de eventos (inmutable)

Reglas de negocio:
  - La base de datos interna es la única fuente de verdad.
  - Nunca se persisten datos externos sin normalizar.
  - Los registros nunca se eliminan físicamente (se usan estados).
  - El stock visible siempre se calcula: min(stock_proveedor, max_stock).
  - El stock siempre se gestiona por variante.
"""
import uuid
import json
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.db import models
from django.conf import settings


# ── Utilidad de cifrado ────────────────────────────────────────────────────

def _cipher() -> Fernet:
    """Retorna un cifrador Fernet usando la ENCRYPTION_KEY del settings."""
    key = settings.ENCRYPTION_KEY
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)


# ── Choices ────────────────────────────────────────────────────────────────

class IntegrationType(models.TextChoices):
    API_REST = 'api_rest', 'API REST'
    WEBHOOK  = 'webhook',  'Solo webhooks'
    CSV      = 'csv',      'Archivo CSV'
    MANUAL   = 'manual',   'Manual'
    MOCK     = 'mock',     'Simulación (sin HTTP — pruebas)'


class ProviderAdapter(models.TextChoices):
    """Adaptador HTTP / formato de payload para envío de pedidos y (futuro) sync."""
    REST_GENERICO = 'rest_generico', 'REST JSON genérico (Bearer + /orders/)'
    DROPI = 'dropi', 'Dropi (payload específico — revisar credenciales)'
    MOCK = 'mock', 'Simulación local (respuesta exitosa sin red)'


class SupplierStatus(models.TextChoices):
    ACTIVO   = 'activo',   'Activo'
    INACTIVO = 'inactivo', 'Inactivo'
    PRUEBA   = 'prueba',   'En prueba'
    ERROR    = 'error',    'Error de conexión'


class SupplierProductStatus(models.TextChoices):
    ACTIVO        = 'activo',        'Activo'
    INACTIVO      = 'inactivo',      'Inactivo'
    SINCRONIZANDO = 'sincronizando', 'Sincronizando'
    ERROR         = 'error',         'Error de sincronización'


class VariantStatus(models.TextChoices):
    ACTIVO   = 'activo',   'Activo'
    AGOTADO  = 'agotado',  'Agotado'
    INACTIVO = 'inactivo', 'Inactivo'


class SupplierOrderStatus(models.TextChoices):
    PENDIENTE_ENVIO = 'pendiente_envio', 'Pendiente de envío'
    ENVIADO         = 'enviado',         'Enviado al proveedor'
    CONFIRMADO      = 'confirmado',      'Confirmado por proveedor'
    EN_TRANSITO     = 'en_transito',     'En tránsito'
    ENTREGADO       = 'entregado',       'Entregado'
    ERROR_PROVEEDOR = 'error_proveedor', 'Error del proveedor'
    CANCELADO       = 'cancelado',       'Cancelado'


class EventType(models.TextChoices):
    WEBHOOK_ENTRANTE = 'webhook_entrante', 'Webhook entrante'
    PEDIDO_ENVIADO   = 'pedido_enviado',   'Pedido enviado'
    PEDIDO_ERROR     = 'pedido_error',     'Error de pedido'
    SYNC_PRODUCTO    = 'sync_producto',    'Sincronización de producto'
    SYNC_STOCK       = 'sync_stock',       'Cambio de stock'
    SYNC_PRECIO      = 'sync_precio',      'Cambio de precio'
    TRACKING_UPDATE  = 'tracking_update',  'Actualización de tracking'
    ERROR            = 'error',            'Error general'


# Aliases for backward compatibility within the codebase
TipoIntegracion = IntegrationType
AdapterProveedor = ProviderAdapter
EstadoProveedor = SupplierStatus
EstadoProductoProveedor = SupplierProductStatus
EstadoVariante = VariantStatus
EstadoPedidoProveedor = SupplierOrderStatus
TipoEvento = EventType


# ── Modelos ────────────────────────────────────────────────────────────────

class Supplier(models.Model):
    """
    Proveedor de dropshipping.
    Las credenciales (API key, secreto, etc.) se almacenan cifradas con Fernet.
    La política de precios define cómo se calcula el precio calculado de cada variante.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name             = models.CharField('Nombre', max_length=200)
    slug             = models.SlugField('Slug', unique=True,
                           help_text='Identificador URL. Se usa en el endpoint de webhook.')
    integration_type = models.CharField(
        'Tipo de integración', max_length=20,
        choices=IntegrationType.choices, default=IntegrationType.API_REST,
    )
    adapter = models.CharField(
        'Adaptador de API', max_length=32,
        choices=ProviderAdapter.choices,
        default=ProviderAdapter.REST_GENERICO,
        help_text='Define el formato de autenticación y payload al enviar pedidos al proveedor.',
    )
    endpoint_base    = models.URLField(
        'Endpoint base', blank=True,
        help_text='URL raíz de la API del proveedor (ej: https://api.proveedor.com/v1)',
    )

    # Credenciales cifradas con Fernet — nunca exponer en texto plano
    _credentials = models.TextField(
        db_column='credenciales', blank=True,
        help_text='JSON cifrado. Usar el campo "credenciales" del formulario.',
    )

    webhook_secret   = models.CharField(
        'Secreto del webhook', max_length=256, blank=True,
        help_text='Clave HMAC para validar la firma de webhooks entrantes.',
    )
    status           = models.CharField(
        'Estado', max_length=20,
        choices=SupplierStatus.choices, default=SupplierStatus.ACTIVO,
    )
    pricing_policy   = models.JSONField(
        'Política de precios', default=dict,
        help_text=(
            'Define cómo calcular el precio final. Ejemplos: '
            '{"tipo": "margen", "valor": 0.30} — sube el precio 30 %; '
            '{"tipo": "multiplicador", "valor": 1.5}; '
            '{"tipo": "fijo", "valor": 5000} — agrega $5.000 fijos.'
        ),
    )
    origin_currency  = models.CharField('Moneda de origen', max_length=3, default='COP')
    stock_buffer     = models.IntegerField(
        'Buffer de stock', default=0,
        help_text='Unidades a descontar del stock reportado (ej: 2 → si proveedor dice 10, se guarda 8).',
    )
    delivery_days    = models.PositiveIntegerField('Días de entrega', default=3)
    notes            = models.TextField('Notas', blank=True)
    created_at       = models.DateTimeField('Creado en', auto_now_add=True)
    updated_at       = models.DateTimeField('Actualizado en', auto_now=True)

    class Meta:
        verbose_name        = 'Proveedor'
        verbose_name_plural = 'Proveedores'
        ordering            = ['name']

    def __str__(self):
        return self.name

    # ── Cifrado/descifrado de credenciales ──────────────────────────────
    @property
    def credenciales(self) -> dict:
        """Retorna las credenciales descifradas como dict."""
        if not self._credentials:
            return {}
        try:
            decrypted = _cipher().decrypt(self._credentials.encode()).decode()
            return json.loads(decrypted)
        except (InvalidToken, Exception):
            return {}

    @credenciales.setter
    def credenciales(self, value: dict):
        """Cifra y guarda las credenciales."""
        if not value:
            self._credentials = ''
            return
        raw = json.dumps(value) if isinstance(value, dict) else str(value)
        self._credentials = _cipher().encrypt(raw.encode()).decode()


class SupplierProduct(models.Model):
    """
    Producto normalizado recibido de un proveedor.
    El campo raw_data conserva el payload original para auditoría.
    El campo local_product vincula este producto al catálogo interno.
    """
    id                  = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supplier            = models.ForeignKey(
        Supplier, on_delete=models.CASCADE,
        related_name='productos', verbose_name='Proveedor',
    )
    supplier_product_id = models.CharField('ID en el proveedor', max_length=200)
    name                = models.CharField('Nombre', max_length=500)
    description         = models.TextField('Descripción', blank=True)
    category_name       = models.CharField(
        'Categoría del proveedor', max_length=200, blank=True,
        help_text='Nombre de categoría tal como la define el proveedor (informativo, solo lectura).',
    )
    local_category      = models.ForeignKey(
        'products.Category', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='supplier_products', verbose_name='Categoría en tu tienda',
        help_text='Categoría de TU catálogo a la que pertenece este producto.',
    )
    status              = models.CharField(
        'Estado', max_length=20,
        choices=SupplierProductStatus.choices, default=SupplierProductStatus.ACTIVO,
    )
    raw_data            = models.JSONField(
        'Datos originales', default=dict,
        help_text='Payload exacto recibido del proveedor. Solo lectura — no editar manualmente.',
    )
    synced_at           = models.DateTimeField('Última sincronización', auto_now=True)
    local_product       = models.ForeignKey(
        'products.Product', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='fuentes_proveedor', verbose_name='Producto local vinculado',
        help_text='Producto del catálogo propio al que pertenece este registro.',
    )
    created_at          = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Producto del proveedor'
        verbose_name_plural = 'Productos del proveedor'
        unique_together     = ('supplier', 'supplier_product_id')
        ordering            = ['-synced_at']

    def __str__(self):
        return f'{self.supplier.name} — {self.name}'


class SupplierVariant(models.Model):
    """
    Variante de un producto del proveedor.
    Stock y precio siempre gestionados a nivel de variante.
    calculated_price = base_price aplicando la pricing_policy del proveedor.
    """
    id                  = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supplier_product    = models.ForeignKey(
        SupplierProduct, on_delete=models.CASCADE,
        related_name='variantes', verbose_name='Producto del proveedor',
    )
    supplier_variant_id = models.CharField('ID de variante en el proveedor', max_length=200)
    sku                 = models.CharField('SKU', max_length=200)
    base_price          = models.DecimalField(
        'Precio base', max_digits=12, decimal_places=2,
        help_text='Precio reportado por el proveedor sin margen.',
    )
    calculated_price    = models.DecimalField(
        'Precio calculado', max_digits=12, decimal_places=2,
        help_text='Precio final aplicando la política de precios del proveedor.',
    )
    stock               = models.IntegerField(
        'Stock disponible (ajustado)', default=0,
        help_text='Stock reportado por el proveedor menos el buffer_stock configurado.',
    )
    attributes          = models.JSONField(
        'Atributos', default=dict,
        help_text='Ej: {"color": "negro", "talla": "M"}',
    )
    status              = models.CharField(
        'Estado', max_length=20,
        choices=VariantStatus.choices, default=VariantStatus.ACTIVO,
    )
    image_url           = models.URLField('URL de imagen', blank=True)
    updated_at          = models.DateTimeField('Última actualización', auto_now=True)

    class Meta:
        verbose_name        = 'Variante del proveedor'
        verbose_name_plural = 'Variantes del proveedor'
        unique_together     = ('supplier_product', 'supplier_variant_id')

    def __str__(self):
        attrs = self.attributes or {}
        name  = attrs.get('name', '') or self.sku
        return name[:100] if name else self.sku


class LinkedProduct(models.Model):
    """
    Vínculo entre una SupplierVariant y un Product del catálogo propio.

    Es la pieza central del sistema de "capped stock sync":
      stock_visible = min(supplier_variant.stock, max_stock)

    Cada vez que el proveedor actualiza el stock, el motor de sincronización:
      1. Recalcula stock_visible con la fórmula.
      2. Escribe el resultado en products.Product.stock (o stock_by_size).
      3. Registra el recalculo en calculated_stock y last_recalculated_at.

    Si sync_enabled=False, el vínculo existe pero el stock NO se actualiza automáticamente.
    Si is_active=False, el vínculo está suspendido (sin actualización ni visualización).
    """
    id                  = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # ── Lado proveedor ───────────────────────────────────────────────
    supplier_variant    = models.ForeignKey(
        SupplierVariant, on_delete=models.CASCADE,
        related_name='vinculos', verbose_name='Variante del proveedor',
    )

    # ── Lado catálogo propio ─────────────────────────────────────────
    local_product       = models.ForeignKey(
        'products.Product', on_delete=models.CASCADE,
        related_name='vinculos_proveedor', verbose_name='Producto local',
    )

    # ── Reglas de stock ──────────────────────────────────────────────
    max_stock           = models.PositiveIntegerField(
        'Stock máximo', default=10,
        help_text=(
            'Límite de stock que el cliente verá, sin importar cuánto tenga el proveedor. '
            'Fórmula: min(stock_proveedor, max_stock)'
        ),
    )

    # ── Precio (override opcional) ───────────────────────────────────
    price_margin        = models.DecimalField(
        'Margen de precio', max_digits=5, decimal_places=4,
        null=True, blank=True,
        help_text='Si se define, sobreescribe la política de precios del proveedor para este producto.',
    )

    # ── Control ─────────────────────────────────────────────────────
    is_active    = models.BooleanField(
        'Activo', default=True,
        help_text='Si está inactivo, el vínculo existe pero no se sincroniza ni afecta al catálogo.',
    )
    sync_enabled = models.BooleanField(
        'Sincronizar', default=True,
        help_text='Si está desactivado, el stock NO se actualiza automáticamente por webhooks.',
    )

    # ── Cache del último cálculo ─────────────────────────────────────
    calculated_stock      = models.IntegerField('Stock calculado', default=0, editable=False)
    last_recalculated_at  = models.DateTimeField('Último recálculo', null=True, blank=True, editable=False)

    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Producto vinculado'
        verbose_name_plural = 'Productos vinculados'
        unique_together     = ('supplier_variant', 'local_product')
        ordering            = ['-created_at']

    def __str__(self):
        return (
            f'{self.supplier_variant.sku} → {self.local_product.name} '
            f'[stock: {self.calculated_stock}/{self.max_stock}]'
        )

    @property
    def stock_proveedor(self) -> int:
        return self.supplier_variant.stock

    @property
    def stock_visible(self) -> int:
        """Fórmula central: min(stock_proveedor, max_stock)."""
        return min(self.stock_proveedor, self.max_stock)


class SupplierOrder(models.Model):
    """
    Pedido enviado (o por enviar) a un proveedor.
    Nunca se elimina — se cambia el estado.
    sent_payload y supplier_response se guardan para auditoría y reintentos.
    """
    id                  = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supplier            = models.ForeignKey(
        Supplier, on_delete=models.PROTECT,
        related_name='pedidos', verbose_name='Proveedor',
    )
    local_order         = models.ForeignKey(
        'orders.Order', on_delete=models.PROTECT,
        related_name='pedidos_proveedor', verbose_name='Pedido local',
    )
    supplier_order_id   = models.CharField('ID del pedido en proveedor', max_length=200, blank=True)
    status              = models.CharField(
        'Estado', max_length=30,
        choices=SupplierOrderStatus.choices, default=SupplierOrderStatus.PENDIENTE_ENVIO,
    )
    total               = models.DecimalField('Total (COP)', max_digits=12, decimal_places=2)
    currency            = models.CharField('Moneda', max_length=3, default='COP')
    sent_payload        = models.JSONField('Payload enviado', null=True, blank=True)
    supplier_response   = models.JSONField('Respuesta del proveedor', null=True, blank=True)
    attempts            = models.PositiveIntegerField('Intentos', default=0)
    created_at          = models.DateTimeField('Fecha de creación', auto_now_add=True)
    updated_at          = models.DateTimeField('Última actualización', auto_now=True)

    class Meta:
        verbose_name        = 'Pedido al proveedor'
        verbose_name_plural = 'Pedidos al proveedor'
        ordering            = ['-created_at']

    def __str__(self):
        return f'Pedido #{self.local_order.order_number} → {self.supplier.name}'


class SupplierTracking(models.Model):
    """
    Información de envío y seguimiento de un pedido al proveedor.
    events_history es una lista JSON [{fecha, estado, descripcion, ubicacion}].
    """
    id                    = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order                 = models.ForeignKey(
        SupplierOrder, on_delete=models.CASCADE,
        related_name='tracking', verbose_name='Pedido',
    )
    supplier_tracking_id  = models.CharField('ID de tracking del proveedor', max_length=200, blank=True)
    tracking_number       = models.CharField('Número de guía', max_length=200, blank=True)
    shipping_status       = models.CharField('Estado de envío', max_length=100)
    carrier               = models.CharField('Transportadora', max_length=200, blank=True)
    tracking_url          = models.URLField('URL de tracking', blank=True)
    events_history        = models.JSONField(
        'Historial de eventos', default=list,
        help_text='Lista cronológica: [{fecha, estado, descripcion, ubicacion}]',
    )
    created_at            = models.DateTimeField(auto_now_add=True)
    updated_at            = models.DateTimeField('Última actualización', auto_now=True)

    class Meta:
        verbose_name        = 'Tracking del proveedor'
        verbose_name_plural = 'Trackings del proveedor'
        ordering            = ['-updated_at']

    def __str__(self):
        return f'Guía {self.tracking_number} — {self.shipping_status}'


class SupplierLog(models.Model):
    """
    Registro de auditoría inmutable de todos los eventos del módulo de proveedores.
    No permite edición ni eliminación desde el admin.
    """
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supplier    = models.ForeignKey(
        Supplier, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='logs', verbose_name='Proveedor',
    )
    event_type  = models.CharField('Tipo de evento', max_length=30, choices=EventType.choices)
    payload     = models.JSONField('Payload', null=True, blank=True)
    response    = models.JSONField('Respuesta', null=True, blank=True)
    status      = models.CharField(
        'Estado', max_length=20,
        choices=[('ok', 'OK'), ('error', 'Error'), ('rechazado', 'Rechazado')],
    )
    message     = models.TextField('Mensaje', blank=True)
    timestamp   = models.DateTimeField('Fecha / hora', auto_now_add=True)

    class Meta:
        verbose_name        = 'Log del proveedor'
        verbose_name_plural = 'Logs del proveedor'
        ordering            = ['-timestamp']

    def __str__(self):
        name = self.supplier.name if self.supplier else 'Sin proveedor'
        return f'[{self.event_type}] {name} — {self.timestamp}'


# ── Aliases para backward compatibility (referencias antiguas en código) ──────
Proveedor = Supplier
ProductoProveedor = SupplierProduct
VarianteProveedor = SupplierVariant
ProductoVinculado = LinkedProduct
PedidoProveedor = SupplierOrder
TrackingProveedor = SupplierTracking
LogProveedor = SupplierLog
