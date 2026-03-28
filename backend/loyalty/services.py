"""
Franja Pixelada — Servicios del Sistema de Fidelidad

Toda la lógica de negocio vive aquí.  Las vistas y señales solo delegan.

Configuración (settings.py / .env):
  LOYALTY_POINTS_PER_COP   int  Unidades COP que generan 1 punto   (default: 1000)
  LOYALTY_POINT_VALUE_COP  int  Valor en COP de 1 punto             (default: 10)
  LOYALTY_MAX_REDEMPTION_PCT float  Máximo del total de la orden redimible (default: 0.20)
  LOYALTY_EXPIRATION_DAYS  int | None  Días hasta expiración; None = sin expiración

Garantías:
  - Saldo nunca negativo.
  - Acumulación y reverso son idempotentes (bandera Order.loyalty_points_processed
    + búsqueda de transacción existente).
  - Toda mutación de saldo usa select_for_update() + F-expressions para evitar
    race conditions con múltiples workers Celery.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import transaction
from django.db.models import F

from loyalty.models import LoyaltyAccount, PointTransaction

if TYPE_CHECKING:
    from orders.models import Order
    from users.models import User

logger = logging.getLogger(__name__)


# ── Configuración ──────────────────────────────────────────────────────────────

def _cfg() -> dict:
    return {
        'points_per_cop': int(getattr(settings, 'LOYALTY_POINTS_PER_COP', 1000)),
        'point_value_cop': int(getattr(settings, 'LOYALTY_POINT_VALUE_COP', 10)),
        'max_redemption_pct': float(getattr(settings, 'LOYALTY_MAX_REDEMPTION_PCT', 0.20)),
    }


# ── Gestión de cuenta ──────────────────────────────────────────────────────────

def get_or_create_account(user: User) -> LoyaltyAccount:
    """Obtiene o crea automáticamente la cuenta de puntos del usuario."""
    account, _ = LoyaltyAccount.objects.get_or_create(user=user)
    return account


# ── Cálculo ────────────────────────────────────────────────────────────────────

def calculate_points_earned(order: Order) -> int:
    """
    Puntos que se generan por una orden.
    Base: order.subtotal (productos; excluye IVA y costo de envío).
    """
    cfg = _cfg()
    return int(float(order.subtotal) // cfg['points_per_cop'])


def calculate_redemption_value(points: int) -> Decimal:
    """Convierte una cantidad de puntos a su equivalente en COP."""
    cfg = _cfg()
    return Decimal(str(points * cfg['point_value_cop']))


def preview_redemption(
    user: User,
    points_to_use: int,
    order_total: Decimal,
) -> dict:
    """
    Calcula el descuento que se aplicaría al usar `points_to_use` puntos.
    No persiste ningún cambio — solo informativo para el frontend.

    Retorna dict con claves:
      valid            bool
      reason           str | None
      points_applied   int   (puede ser < points_to_use si se aplica el límite %)
      discount_amount  float (COP)
      points_balance   int
      max_redemption_pct float
      point_value_cop  int
    """
    cfg = _cfg()

    if points_to_use <= 0:
        return {
            'valid': False,
            'reason': 'La cantidad de puntos debe ser mayor a cero.',
            'points_applied': 0,
            'discount_amount': 0,
            'points_balance': 0,
            'max_redemption_pct': cfg['max_redemption_pct'],
            'point_value_cop': cfg['point_value_cop'],
        }

    account = get_or_create_account(user)

    if points_to_use > account.points_balance:
        return {
            'valid': False,
            'reason': f'Saldo insuficiente. Disponible: {account.points_balance} pts.',
            'points_applied': 0,
            'discount_amount': 0,
            'points_balance': account.points_balance,
            'max_redemption_pct': cfg['max_redemption_pct'],
            'point_value_cop': cfg['point_value_cop'],
        }

    raw_discount = calculate_redemption_value(points_to_use)
    max_allowed = Decimal(str(float(order_total) * cfg['max_redemption_pct']))

    if raw_discount > max_allowed:
        # Truncar al máximo permitido por la política
        max_pts = int(float(max_allowed) // cfg['point_value_cop'])
        points_applied = max_pts
        discount = calculate_redemption_value(max_pts)
    else:
        points_applied = points_to_use
        discount = raw_discount

    return {
        'valid': True,
        'reason': None,
        'points_applied': points_applied,
        'discount_amount': float(discount),
        'points_balance': account.points_balance,
        'max_redemption_pct': cfg['max_redemption_pct'],
        'point_value_cop': cfg['point_value_cop'],
    }


# ── Acumulación (post-pago) ────────────────────────────────────────────────────

def assign_points_for_order(order: Order) -> PointTransaction | None:
    """
    Asigna puntos al usuario tras confirmar el pago de una orden.

    Condiciones para ejecutar:
      - order.user_id no nulo
      - order.payment_status == 'paid'
      - order.loyalty_points_processed == False

    Idempotencia:
      - Verifica la bandera loyalty_points_processed.
      - Dentro de la tx atómica verifica que no exista ya una transacción EARN.
      - Usa select_for_update() para serializar escrituras concurrentes.

    Retorna la PointTransaction creada, o None si no corresponde acumular.
    """
    if not order.user_id:
        return None
    if order.payment_status != 'paid':
        logger.warning(
            'assign_points_for_order: orden %s con payment_status=%s, se esperaba paid.',
            order.order_number, order.payment_status,
        )
        return None
    if order.loyalty_points_processed:
        logger.info('Orden %s ya procesada para fidelidad. Skip.', order.order_number)
        return None

    points = calculate_points_earned(order)

    if points <= 0:
        # Marcar procesada aunque no haya puntos (subtotal muy bajo)
        from orders.models import Order as OrderModel
        OrderModel.objects.filter(pk=order.pk).update(loyalty_points_processed=True)
        return None

    with transaction.atomic():
        # Verificar idempotencia dentro de la transacción
        exists = PointTransaction.objects.filter(
            account__user_id=order.user_id,
            order=order,
            transaction_type=PointTransaction.TransactionType.EARN,
        ).exists()
        if exists:
            logger.info(
                'Transacción EARN ya existe para orden %s. Skip.',
                order.order_number,
            )
            return None

        account, _ = LoyaltyAccount.objects.select_for_update().get_or_create(
            user_id=order.user_id,
        )

        new_balance = account.points_balance + points
        tx = PointTransaction.objects.create(
            account=account,
            transaction_type=PointTransaction.TransactionType.EARN,
            points=points,
            balance_after=new_balance,
            order=order,
            description=f'Acumulación por orden #{order.order_number}',
            metadata={
                'order_number': order.order_number,
                'subtotal': str(order.subtotal),
            },
        )

        LoyaltyAccount.objects.filter(pk=account.pk).update(
            points_balance=F('points_balance') + points,
            total_earned=F('total_earned') + points,
        )

        from orders.models import Order as OrderModel
        OrderModel.objects.filter(pk=order.pk).update(
            loyalty_points_earned=points,
            loyalty_points_processed=True,
        )

    logger.info(
        'Asignados %d pts a %s por orden %s.',
        points, order.user_id, order.order_number,
    )
    return tx


# ── Redención (al crear la orden) ─────────────────────────────────────────────

def redeem_points_for_order(
    user: User,
    order: Order,
    points_to_use: int,
) -> PointTransaction:
    """
    Descuenta puntos del saldo al crear una orden.
    Debe llamarse dentro de la misma transaction.atomic() del checkout
    para que la operación sea completamente atómica con la creación de la orden.

    Raises:
        ValueError: Saldo insuficiente o cantidad inválida.
    """
    if points_to_use <= 0:
        raise ValueError('La cantidad de puntos debe ser mayor a cero.')

    with transaction.atomic():
        account, _ = LoyaltyAccount.objects.select_for_update().get_or_create(user=user)

        if points_to_use > account.points_balance:
            raise ValueError(
                f'Saldo insuficiente. Disponible: {account.points_balance} pts.'
            )

        discount = calculate_redemption_value(points_to_use)
        new_balance = account.points_balance - points_to_use

        tx = PointTransaction.objects.create(
            account=account,
            transaction_type=PointTransaction.TransactionType.REDEEM,
            points=-points_to_use,
            balance_after=new_balance,
            order=order,
            description=f'Redención en orden #{order.order_number}',
            metadata={
                'order_number': order.order_number,
                'discount_amount': str(discount),
            },
        )

        LoyaltyAccount.objects.filter(pk=account.pk).update(
            points_balance=F('points_balance') - points_to_use,
            total_redeemed=F('total_redeemed') + points_to_use,
        )

    logger.info(
        'Redimidos %d pts de %s en orden %s (COP %s).',
        points_to_use, user.email, order.order_number, discount,
    )
    return tx


# ── Reverso (cancelación / reembolso) ─────────────────────────────────────────

def reverse_points_for_order(order: Order) -> list[PointTransaction]:
    """
    Revierte puntos ganados y devuelve puntos usados cuando una orden
    es cancelada o reembolsada.

    Idempotente: verifica la existencia de transacciones REVERSE_* previas
    antes de crear nuevas.

    Retorna la lista de PointTransaction creadas (puede ser vacía).
    """
    if not order.user_id:
        return []

    created: list[PointTransaction] = []

    with transaction.atomic():
        try:
            account = LoyaltyAccount.objects.select_for_update().get(
                user_id=order.user_id,
            )
        except LoyaltyAccount.DoesNotExist:
            return []

        # 1. Revertir puntos ganados
        if order.loyalty_points_earned > 0:
            already = PointTransaction.objects.filter(
                account=account,
                order=order,
                transaction_type=PointTransaction.TransactionType.REVERSE_EARN,
            ).exists()
            if not already:
                pts = order.loyalty_points_earned
                new_balance = account.points_balance - pts
                tx = PointTransaction.objects.create(
                    account=account,
                    transaction_type=PointTransaction.TransactionType.REVERSE_EARN,
                    points=-pts,
                    balance_after=new_balance,
                    order=order,
                    description=(
                        f'Reverso de acumulación — orden #{order.order_number} '
                        f'cancelada/reembolsada'
                    ),
                    metadata={'order_number': order.order_number},
                )
                LoyaltyAccount.objects.filter(pk=account.pk).update(
                    points_balance=F('points_balance') - pts,
                    total_earned=F('total_earned') - pts,
                )
                account.refresh_from_db(fields=['points_balance'])
                created.append(tx)
                logger.info(
                    'Revertidos %d pts ganados de orden %s.',
                    pts, order.order_number,
                )

        # 2. Devolver puntos usados (si el usuario usó puntos al hacer el pedido)
        if order.loyalty_points_used > 0:
            already = PointTransaction.objects.filter(
                account=account,
                order=order,
                transaction_type=PointTransaction.TransactionType.REVERSE_REDEEM,
            ).exists()
            if not already:
                pts = order.loyalty_points_used
                new_balance = account.points_balance + pts
                tx = PointTransaction.objects.create(
                    account=account,
                    transaction_type=PointTransaction.TransactionType.REVERSE_REDEEM,
                    points=pts,
                    balance_after=new_balance,
                    order=order,
                    description=(
                        f'Devolución de puntos usados — orden #{order.order_number} '
                        f'cancelada/reembolsada'
                    ),
                    metadata={'order_number': order.order_number},
                )
                LoyaltyAccount.objects.filter(pk=account.pk).update(
                    points_balance=F('points_balance') + pts,
                    total_redeemed=F('total_redeemed') - pts,
                )
                created.append(tx)
                logger.info(
                    'Devueltos %d pts usados de orden %s.',
                    pts, order.order_number,
                )

    return created
