"""
Franja Pixelada — Modelos de Pagos
Soporta Stripe y PayPal
"""
from django.db import models
import uuid


class Payment(models.Model):
    """Registro de transacciones de pago"""
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('processing', 'Procesando'),
        ('succeeded', 'Exitoso'),
        ('failed', 'Fallido'),
        ('refunded', 'Reembolsado'),
        ('cancelled', 'Cancelado'),
    ]

    METHOD_CHOICES = [
        ('stripe', 'Stripe'),
        ('paypal', 'PayPal'),
        ('cash', 'Efectivo'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        'orders.Order', on_delete=models.PROTECT, related_name='payments'
    )
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, verbose_name='Método de pago')
    payment_id = models.CharField(
        max_length=200, blank=True, db_index=True,
        help_text='ID de la transacción en Stripe o PayPal'
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Monto (COP)')
    currency = models.CharField(max_length=3, default='COP')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    raw_response = models.JSONField(default=dict, blank=True, verbose_name='Respuesta del proveedor')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pago'
        verbose_name_plural = 'Pagos'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_method_display()} — {self.amount} {self.currency} ({self.get_status_display()})'
