"""
Franja Pixelada — Modelos de Pedidos
Incluye: Cart, CartItem, Address, Order, OrderItem, Coupon
Los CartItem y OrderItem soportan personalización (bordado / grupo sanguíneo)
"""
import uuid

from django.core.validators import MinValueValidator
from django.db import IntegrityError, models

from products.validators import validate_image_file


class Cart(models.Model):
    """Carrito de compras (por usuario o por sesión)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        'users.User', on_delete=models.CASCADE,
        null=True, blank=True, related_name='cart'
    )
    session_key = models.CharField(max_length=100, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Carrito'
        verbose_name_plural = 'Carritos'

    def __str__(self):
        owner = self.user.email if self.user else f'Sesión:{self.session_key[:8]}'
        return f'Carrito de {owner}'

    @property
    def total_items(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def subtotal(self):
        return sum(item.line_total for item in self.items.all())


class CartItem(models.Model):
    """Ítem dentro del carrito — soporta talla y personalización"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    variant = models.ForeignKey(
        'products.ProductVariant', on_delete=models.SET_NULL,
        null=True, blank=True
    )

    # Selección del cliente
    talla = models.CharField(max_length=10, blank=True)

    # Personalización (parche de apellido / grupo sanguíneo)
    bordado = models.CharField(
        max_length=30, blank=True,
        verbose_name='Texto bordado',
        help_text='Apellido para el parche de identificación'
    )
    rh = models.CharField(
        max_length=5, blank=True,
        verbose_name='Grupo sanguíneo (RH)',
        help_text='Ej: O+, A−, AB+'
    )

    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    price_at_addition = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Ítem de Carrito'
        verbose_name_plural = 'Ítems de Carrito'
        # Los ítems personalizados NUNCA se fusionan, por eso bordado y rh entran en unique_together
        unique_together = ['cart', 'product', 'variant', 'talla', 'bordado', 'rh']

    def __str__(self):
        extra = []
        if self.talla:
            extra.append(f'Talla {self.talla}')
        if self.bordado:
            extra.append(f'Bordado: {self.bordado}')
        if self.rh:
            extra.append(f'RH: {self.rh}')
        suffix = f' ({", ".join(extra)})' if extra else ''
        return f'{self.product.name}{suffix} x{self.quantity}'

    @property
    def line_total(self):
        price = self.variant.final_price if self.variant else self.product.price
        return price * self.quantity


class Address(models.Model):
    """Dirección de envío / facturación"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='addresses')
    full_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20)
    country = models.CharField(max_length=100, default='Colombia')
    department = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Dirección'
        verbose_name_plural = 'Direcciones'

    def __str__(self):
        return f'{self.full_name} — {self.city}, {self.department}'

    def save(self, *args, **kwargs):
        if self.is_default:
            Address.objects.filter(
                user=self.user, is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class PaymentMethod(models.TextChoices):
    """Método de pago registrado en la orden."""
    NEKI = 'neki', 'Neki (comprobante manual)'


class ManualPaymentStatus(models.TextChoices):
    """
    Flujo comprobante manual (Neki): pendiente → verificado o rechazado por admin.
    Vacío = no aplica (órdenes con otro flujo de pago).
    """
    PENDING = 'PENDING', 'Pendiente verificación'
    PAID = 'PAID', 'Comprobante recibido'
    VERIFIED = 'VERIFIED', 'Pago verificado'
    REJECTED = 'REJECTED', 'Pago rechazado'


# Transiciones válidas para manual_payment_status.
# Estados terminales (VERIFIED, REJECTED) no tienen salida.
_VALID_MANUAL_PAYMENT_TRANSITIONS: dict[str, set[str]] = {
    '': {ManualPaymentStatus.PENDING},
    ManualPaymentStatus.PENDING: {ManualPaymentStatus.PAID, ManualPaymentStatus.VERIFIED, ManualPaymentStatus.REJECTED},
    ManualPaymentStatus.PAID: {ManualPaymentStatus.VERIFIED, ManualPaymentStatus.REJECTED},
    ManualPaymentStatus.VERIFIED: set(),   # estado terminal — sin retroceso
    ManualPaymentStatus.REJECTED: set(),   # estado terminal — sin retroceso
}


class Order(models.Model):
    """Orden de compra completa"""
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('confirmed', 'Confirmada'),
        ('processing', 'Procesando'),
        ('shipped', 'Enviada'),
        ('delivered', 'Entregada'),
        ('cancelled', 'Cancelada'),
        ('refunded', 'Reembolsada'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('paid', 'Pagada'),
        ('failed', 'Fallida'),
        ('refunded', 'Reembolsada'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(max_length=20, unique=True, db_index=True)
    user = models.ForeignKey(
        'users.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='orders'
    )

    # Datos de envío (snapshot al momento del pedido)
    shipping_full_name = models.CharField(max_length=200)
    shipping_phone = models.CharField(max_length=20)
    shipping_country = models.CharField(max_length=100)
    shipping_department = models.CharField(max_length=100)
    shipping_city = models.CharField(max_length=100)
    shipping_address_line1 = models.CharField(max_length=255)
    shipping_address_line2 = models.CharField(max_length=255, blank=True)
    shipping_postal_code = models.CharField(max_length=20, blank=True)

    email = models.EmailField()

    # Totales (COP)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)

    # Estado
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    payment_method = models.CharField(
        max_length=50,
        blank=True,
        help_text='Ej: neki, stripe. Solo Neki usa comprobante manual.',
    )
    payment_id = models.CharField(max_length=200, blank=True, db_index=True)

    # Pago manual Neki (comprobante)
    payment_proof = models.ImageField(
        upload_to='protected/payment_proofs/neki/%Y/%m/',
        blank=True,
        null=True,
        verbose_name='Comprobante de pago',
        validators=[validate_image_file],
    )
    manual_payment_status = models.CharField(
        'Estado comprobante manual',
        max_length=20,
        choices=ManualPaymentStatus.choices,
        blank=True,
        default='',
        db_index=True,
        help_text='PENDIENTE/VERIFICADO solo para pagos con comprobante (Neki).',
    )
    providers_dispatch_enqueued_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
        help_text='Cuándo se encoló el envío a proveedores (idempotencia).',
    )

    # Envío
    tracking_number = models.CharField(max_length=100, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    # Notas
    customer_notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)

    # Cupón
    coupon_code = models.CharField(max_length=50, blank=True)

    # Puntos de fidelidad
    loyalty_points_used = models.PositiveIntegerField(
        default=0,
        verbose_name='Puntos usados',
        help_text='Puntos de fidelidad aplicados como descuento en esta orden.',
    )
    loyalty_discount_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='Descuento por puntos (COP)',
        help_text='Valor en COP descontado gracias a puntos de fidelidad.',
    )
    loyalty_points_earned = models.PositiveIntegerField(
        default=0,
        editable=False,
        verbose_name='Puntos ganados',
        help_text='Puntos acreditados al usuario tras confirmar el pago.',
    )
    loyalty_points_processed = models.BooleanField(
        default=False,
        editable=False,
        db_index=True,
        verbose_name='Puntos procesados',
        help_text='Bandera de idempotencia: True cuando los puntos ya fueron acreditados.',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Orden'
        verbose_name_plural = 'Órdenes'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'payment_status']),
            models.Index(fields=['-created_at']),
            models.Index(fields=['email']),
            models.Index(fields=['manual_payment_status']),
        ]

    def __str__(self):
        return f'Orden #{self.order_number}'

    @property
    def total_amount(self):
        """Alias del total para APIs (compatibilidad con naming externo)."""
        return self.total

    def clean(self):
        """Valida que la transición de manual_payment_status sea permitida."""
        from django.core.exceptions import ValidationError

        if not self.pk or not self.manual_payment_status:
            return  # creación o sin pago manual: no validar

        try:
            prev_status = Order.objects.only('manual_payment_status').get(pk=self.pk).manual_payment_status
        except Order.DoesNotExist:
            return

        if prev_status == self.manual_payment_status:
            return  # sin cambio, nada que validar

        valid_next = _VALID_MANUAL_PAYMENT_TRANSITIONS.get(prev_status, set())
        if self.manual_payment_status not in valid_next:
            etiquetas = ', '.join(valid_next) if valid_next else '(ninguna — estado terminal)'
            raise ValidationError({
                'manual_payment_status': (
                    f'Transición inválida: "{prev_status or "(vacío)"}" → "{self.manual_payment_status}". '
                    f'Transiciones permitidas: {etiquetas}.'
                )
            })

    def save(self, *args, **kwargs):
        import uuid

        if self.order_number:
            super().save(*args, **kwargs)
            return

        # UUID hex proporciona ~10^12 combinaciones: colisión prácticamente imposible.
        # 3 reintentos como salvaguarda ante improbables colisiones.
        for _ in range(3):
            self.order_number = f'FP{uuid.uuid4().hex[:10].upper()}'
            try:
                super().save(*args, **kwargs)
                return
            except IntegrityError:
                self.order_number = ''
                continue
        raise IntegrityError('No se pudo generar un número de orden único.')


class OrderItem(models.Model):
    """Ítem dentro de una orden — incluye personalización"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(
        'products.Product', on_delete=models.SET_NULL, null=True
    )
    variant = models.ForeignKey(
        'products.ProductVariant', on_delete=models.SET_NULL, null=True, blank=True
    )

    # Snapshot al momento de la compra
    product_name = models.CharField(max_length=200)
    product_sku = models.CharField(max_length=50)
    variant_name = models.CharField(max_length=100, blank=True)
    talla = models.CharField(max_length=10, blank=True)

    # Personalización (snapshot)
    bordado = models.CharField(max_length=30, blank=True, verbose_name='Texto bordado')
    rh = models.CharField(max_length=5, blank=True, verbose_name='Grupo sanguíneo')

    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = 'Ítem de Orden'
        verbose_name_plural = 'Ítems de Orden'

    def __str__(self):
        return f'{self.product_name} x{self.quantity}'


class Coupon(models.Model):
    """Cupones de descuento"""
    DISCOUNT_TYPE_CHOICES = [
        ('percentage', 'Porcentaje'),
        ('fixed', 'Valor fijo (COP)'),
    ]

    code = models.CharField(max_length=50, unique=True, db_index=True)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    minimum_purchase = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    max_uses = models.PositiveIntegerField(null=True, blank=True, verbose_name='Usos máximos', help_text='Deja vacío para usos ilimitados.')
    uses_count = models.PositiveIntegerField(default=0, verbose_name='Veces usado')
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Cupón'
        verbose_name_plural = 'Cupones'

    def __str__(self):
        return self.code

    @property
    def is_valid(self):
        from django.utils import timezone
        now = timezone.now()
        if not self.is_active:
            return False
        if now < self.valid_from or now > self.valid_until:
            return False
        if self.max_uses and self.uses_count >= self.max_uses:
            return False
        return True
