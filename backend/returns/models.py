"""
Franja Pixelada — Módulo de Devoluciones

Entidades:
  ReturnRequest  — solicitud principal (1 por orden, múltiples ítems)
  ReturnItem     — línea de devolución (producto/variante + cantidad)
  ReturnEvidence — imágenes de evidencia adjuntadas por el cliente
  ReturnAuditLog — historial inmutable de cambios de estado
"""
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


# ── Catálogos ────────────────────────────────────────────────────────────────

REASON_CHOICES = [
    ('regret',        'Me arrepentí de la compra'),
    ('wrong_product', 'Producto diferente al solicitado'),
    ('defective',     'Producto defectuoso'),
    ('incomplete',    'Producto incompleto'),
    ('damaged',       'Producto dañado en transporte'),
    ('other',         'Otro'),
]

STATUS_CHOICES = [
    ('requested',            'Solicitada'),
    ('reviewing',            'En revisión'),
    ('approved',             'Aprobada'),
    ('rejected_subsanable',  'Rechazada (subsanable)'),
    ('rejected_definitive',  'Rechazada (definitiva)'),
    ('in_transit',           'En envío (cliente devuelve)'),
    ('received',             'Recibida'),
    ('validated',            'Validada'),
    ('refunded',             'Reembolsada'),
    ('closed',               'Cerrada'),
]

PIPELINE_ACTIVE_STATUSES = frozenset({
    'requested', 'reviewing', 'approved', 'in_transit', 'received', 'validated', 'refunded',
})

# Transiciones válidas: cada estado puede avanzar solo a los listados
VALID_TRANSITIONS = {
    'requested':  ['reviewing', 'rejected_subsanable', 'rejected_definitive'],
    'reviewing':  ['approved', 'rejected_subsanable', 'rejected_definitive'],
    'approved':   ['in_transit'],
    'in_transit': ['received'],
    'received':   ['validated', 'rejected_subsanable', 'rejected_definitive'],
    'validated':  ['refunded'],
    'refunded':   ['closed'],
    'rejected_subsanable':  ['closed'],
    'rejected_definitive':  ['closed'],
    'closed':     [],
}

REFUND_METHOD_CHOICES = [
    ('original',     'Método de pago original'),
    ('store_credit', 'Crédito en tienda'),
    ('bank_transfer','Transferencia bancaria'),
]

REFUND_STATUS_CHOICES = [
    ('pending',    'Pendiente'),
    ('partial',    'Reembolso parcial'),
    ('full',       'Reembolso total'),
    ('denied',     'Denegado'),
    ('processed',  'Procesado'),
]

# Ventanas de devolución
RETURN_WINDOW_DAYS_NEW = 30
RETURN_WINDOW_DAYS_USED = 14
RETURN_SHIPMENT_WINDOW_DAYS = 5


# ── Modelos ──────────────────────────────────────────────────────────────────

class ReturnRequest(models.Model):
    """Solicitud de devolución — puede haber varias por orden si las anteriores fueron rechazadas."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='return_requests', verbose_name='Cliente'
    )
    order = models.ForeignKey(
        'orders.Order', on_delete=models.PROTECT,
        related_name='return_requests', verbose_name='Orden'
    )
    parent_return = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='child_returns', verbose_name='Solicitud anterior',
    )
    attempt_number = models.PositiveSmallIntegerField(
        default=1, verbose_name='Número de intento',
    )

    # Motivo
    reason        = models.CharField(max_length=20, choices=REASON_CHOICES, verbose_name='Motivo')
    reason_detail = models.TextField(blank=True, verbose_name='Detalle del motivo')

    # Estado
    status = models.CharField(
        max_length=22, choices=STATUS_CHOICES,
        default='requested', db_index=True, verbose_name='Estado'
    )

    # Notas
    customer_notes = models.TextField(blank=True, verbose_name='Observaciones del cliente')
    admin_notes    = models.TextField(blank=True, verbose_name='Notas internas (admin)')
    rejection_reason = models.TextField(
        blank=True,
        verbose_name='Motivo de rechazo (visible al cliente)',
    )
    rejected_at = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de rechazo')

    # Reembolso
    refund_method  = models.CharField(
        max_length=20, choices=REFUND_METHOD_CHOICES,
        blank=True, verbose_name='Método de reembolso'
    )
    refund_status  = models.CharField(
        max_length=20, choices=REFUND_STATUS_CHOICES,
        default='pending', verbose_name='Estado del reembolso'
    )
    refund_amount  = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Monto reembolsado'
    )
    refund_at      = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de reembolso')
    estimated_refund_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha estimada de reembolso',
    )
    return_code = models.CharField(
        max_length=24,
        unique=True,
        db_index=True,
        blank=True,
        verbose_name='Código de devolución',
    )
    shipping_deadline_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha límite de envío del cliente',
    )

    # Fechas
    requested_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de solicitud')
    resolved_at  = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de resolución')
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Devolución'
        verbose_name_plural = 'Devoluciones'
        ordering = ['-requested_at']

    def __str__(self):
        return f'Devolución #{str(self.id)[:8]} — {self.order.order_number}'

    # ── Lógica de negocio ────────────────────────────────────────────────────

    def can_transition_to(self, new_status):
        return new_status in VALID_TRANSITIONS.get(self.status, [])

    def transition(self, new_status, changed_by=None, note=''):
        if not self.can_transition_to(new_status):
            raise ValueError(
                f'Transición inválida: {self.status} → {new_status}'
            )
        old_status = self.status
        self.status = new_status
        if new_status in (
            'approved', 'rejected_subsanable', 'rejected_definitive',
            'refunded', 'closed',
        ):
            self.resolved_at = timezone.now()
        if new_status == 'approved':
            self.shipping_deadline_at = timezone.now() + timedelta(days=RETURN_SHIPMENT_WINDOW_DAYS)
        if new_status == 'refunded':
            self.refund_at = timezone.now()
            self.refund_status = 'processed'
            if not self.estimated_refund_at:
                self.estimated_refund_at = timezone.now()
        self.save(update_fields=[
            'status',
            'resolved_at',
            'refund_at',
            'refund_status',
            'shipping_deadline_at',
            'estimated_refund_at',
            'updated_at',
        ])
        ReturnAuditLog.objects.create(
            return_request=self,
            from_status=old_status,
            to_status=new_status,
            changed_by=changed_by,
            note=note,
        )

    @property
    def is_active(self):
        return self.status not in (
            'closed', 'rejected_subsanable', 'rejected_definitive', 'refunded',
        )

    @classmethod
    def can_create_for_order(cls, order, parent_return=None):
        """Valida permitir POST de nueva solicitud (pedido o reintento con parent_return)."""
        max_attempts = int(getattr(settings, 'RETURN_MAX_ATTEMPTS_PER_ORDER', 3))
        if order.status != 'delivered':
            return False, 'Solo se pueden devolver órdenes entregadas.'

        qs = cls.objects.filter(order=order)
        if qs.count() >= max_attempts:
            return False, 'Has alcanzado el número máximo de intentos para este pedido.'

        if qs.filter(status='rejected_definitive').exists():
            return False, (
                'Este producto no cumple con las condiciones de devolución según nuestras políticas.'
            )

        if qs.filter(status__in=PIPELINE_ACTIVE_STATUSES).exists():
            return False, 'Ya existe una devolución en curso para esta orden.'

        if qs.filter(status='closed').exclude(refund_status='denied').exists():
            return False, 'Esta orden ya cuenta con una devolución completada.'

        if parent_return is not None:
            if parent_return.order_id != order.id:
                return False, 'La devolución anterior no corresponde a este pedido.'
            if parent_return.status != 'rejected_subsanable':
                return False, 'Solo puedes reintentar una devolución rechazada subsanable.'
            nxt = (parent_return.attempt_number or 1) + 1
            if nxt > max_attempts:
                return False, 'Has alcanzado el número máximo de intentos para este pedido.'
        else:
            if qs.filter(status='rejected_subsanable').exists():
                return False, (
                    'Tienes una devolución rechazada subsanable. '
                    'Abre su detalle y usa “Intentar nuevamente la devolución”.'
                )

        delivered_at = order.delivered_at or order.updated_at
        days_since = max(0, (timezone.now() - delivered_at).days)
        if days_since > RETURN_WINDOW_DAYS_NEW:
            return False, f'El plazo de devolución ({RETURN_WINDOW_DAYS_NEW} días) ha vencido.'
        excluded_slugs = set(getattr(settings, 'RETURN_EXCLUDED_CATEGORY_SLUGS', []))
        exclude_digital = bool(getattr(settings, 'RETURN_EXCLUDE_DIGITAL_PRODUCTS', True))
        special_prefixes = tuple(getattr(settings, 'RETURN_SPECIAL_SKU_PREFIXES', ['DIGI-', 'SPC-']))
        for item in order.items.select_related('product'):
            product = item.product
            if not product:
                continue
            if excluded_slugs and product.category and product.category.slug in excluded_slugs:
                return False, 'Esta orden contiene productos con categoría excluida para devoluciones.'
            if exclude_digital and str(product.sku or '').upper().startswith(special_prefixes):
                return False, 'Esta orden contiene productos no elegibles para devolución.'
        return True, ''

    def save(self, *args, **kwargs):
        if not self.return_code:
            self.return_code = f"DEV-{str(uuid.uuid4())[:8].upper()}"
        super().save(*args, **kwargs)


class ReturnItem(models.Model):
    """Línea dentro de una solicitud — producto + cantidad a devolver."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    return_request = models.ForeignKey(
        ReturnRequest, on_delete=models.CASCADE,
        related_name='items', verbose_name='Solicitud'
    )
    order_item = models.ForeignKey(
        'orders.OrderItem', on_delete=models.PROTECT,
        related_name='return_items', verbose_name='Ítem de orden'
    )
    quantity   = models.PositiveIntegerField(default=1, verbose_name='Cantidad a devolver')
    condition  = models.CharField(
        max_length=20,
        choices=[('unused', 'Sin uso'), ('used', 'Con uso'), ('damaged', 'Dañado')],
        default='unused', verbose_name='Estado del producto'
    )
    has_original_packaging = models.BooleanField(default=True, verbose_name='Tiene empaque original')

    class Meta:
        verbose_name = 'Ítem de devolución'
        verbose_name_plural = 'Ítems de devolución'
        unique_together = [('return_request', 'order_item')]

    def __str__(self):
        return f'{self.order_item.product_name} x{self.quantity}'


class ReturnEvidence(models.Model):
    """Imagen de evidencia subida por el cliente."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    return_request = models.ForeignKey(
        ReturnRequest, on_delete=models.CASCADE,
        related_name='evidence', verbose_name='Solicitud'
    )
    image      = models.ImageField(
        upload_to='returns/evidence/%Y/%m/',
        verbose_name='Imagen'
    )
    caption    = models.CharField(max_length=200, blank=True, verbose_name='Descripción')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Evidencia'
        verbose_name_plural = 'Evidencias'

    def __str__(self):
        return f'Evidencia de {self.return_request}'


class ReturnAuditLog(models.Model):
    """Historial inmutable de cambios de estado — solo append."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    return_request = models.ForeignKey(
        ReturnRequest, on_delete=models.CASCADE,
        related_name='audit_log', verbose_name='Solicitud'
    )
    from_status = models.CharField(max_length=22, verbose_name='Estado anterior')
    to_status   = models.CharField(max_length=22, verbose_name='Estado nuevo')
    changed_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name='Cambiado por'
    )
    note        = models.TextField(blank=True, verbose_name='Nota')
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Auditoría de devolución'
        verbose_name_plural = 'Auditoría de devoluciones'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.from_status} → {self.to_status} ({self.created_at:%d/%m/%Y %H:%M})'
