"""
Franja Pixelada — Modelos del Sistema de Fidelidad

LoyaltyAccount : cuenta 1:1 con el usuario, almacena saldo y totales históricos.
PointTransaction: registro inmutable de cada operación de puntos.

Reglas de inmutabilidad en PointTransaction:
  - No se editan ni eliminan (ver admin.py).
  - Cada operación crea una fila nueva; el balance_after es el saldo resultante.
"""
import uuid

from django.db import models


class LoyaltyAccount(models.Model):
    """Cuenta de puntos de fidelidad — relación 1:1 con User."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        'users.User',
        on_delete=models.CASCADE,
        related_name='loyalty_account',
        verbose_name='Usuario',
    )
    points_balance = models.IntegerField(
        default=0,
        verbose_name='Saldo actual (pts)',
        help_text='Puntos disponibles para redimir.',
    )
    total_earned = models.IntegerField(
        default=0,
        verbose_name='Total acumulado histórico (pts)',
    )
    total_redeemed = models.IntegerField(
        default=0,
        verbose_name='Total redimido histórico (pts)',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Creada el')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Actualizada el')

    class Meta:
        verbose_name = 'Cuenta de Fidelidad'
        verbose_name_plural = 'Cuentas de Fidelidad'
        indexes = [
            models.Index(fields=['user']),
        ]

    def __str__(self):
        return f'{self.user.email} — {self.points_balance} pts'


class PointTransaction(models.Model):
    """
    Registro inmutable de cada operación de puntos.

    points > 0 → crédito (acumulación, reverso de redención, ajuste positivo)
    points < 0 → débito  (redención, reverso de acumulación, ajuste negativo)
    """

    class TransactionType(models.TextChoices):
        EARN = 'earn', 'Acumulación'
        REDEEM = 'redeem', 'Redención'
        REVERSE_EARN = 'reverse_earn', 'Reverso de acumulación'
        REVERSE_REDEEM = 'reverse_redeem', 'Reverso de redención'
        ADJUSTMENT = 'adjustment', 'Ajuste manual'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(
        LoyaltyAccount,
        on_delete=models.CASCADE,
        related_name='transactions',
        verbose_name='Cuenta',
    )
    transaction_type = models.CharField(
        max_length=20,
        choices=TransactionType.choices,
        db_index=True,
        verbose_name='Tipo',
    )
    points = models.IntegerField(
        verbose_name='Puntos',
        help_text='Positivo = crédito, negativo = débito.',
    )
    balance_after = models.IntegerField(
        verbose_name='Saldo resultante',
        help_text='Saldo de la cuenta inmediatamente después de esta transacción.',
    )
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='loyalty_transactions',
        verbose_name='Orden',
    )
    description = models.TextField(blank=True, verbose_name='Descripción')
    metadata = models.JSONField(default=dict, blank=True, verbose_name='Metadata')
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name='Fecha',
    )

    class Meta:
        verbose_name = 'Transacción de Puntos'
        verbose_name_plural = 'Transacciones de Puntos'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['account', '-created_at']),
            models.Index(fields=['order']),
        ]

    def __str__(self):
        sign = '+' if self.points > 0 else ''
        return (
            f'{self.get_transaction_type_display()} '
            f'{sign}{self.points} pts → saldo {self.balance_after}'
        )
