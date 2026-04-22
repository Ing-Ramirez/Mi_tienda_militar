"""
Operaciones atómicas sobre el modelo Coupon.

increment_coupon_uses  → se llama al confirmar pago (Neki VERIFIED / Stripe webhook).
decrement_coupon_uses  → se llama al cancelar o reembolsar una orden.

Ambas usan select_for_update() + F() para evitar race conditions bajo concurrencia.
"""
from __future__ import annotations

import logging

from django.db import transaction
from django.db.models import F

logger = logging.getLogger(__name__)


def increment_coupon_uses(coupon_code: str) -> None:
    """Incrementa en 1 el contador de usos del cupón de forma atómica."""
    if not coupon_code:
        return
    with transaction.atomic():
        updated = (
            _coupon_qs(coupon_code)
            .update(uses_count=F('uses_count') + 1)
        )
    if updated:
        logger.info('Cupón %s: uses_count incrementado', coupon_code.upper())
    else:
        logger.warning('Cupón %s no encontrado o inactivo al intentar incrementar uses_count', coupon_code.upper())


def decrement_coupon_uses(coupon_code: str) -> None:
    """Decrementa en 1 el contador de usos del cupón (nunca por debajo de 0)."""
    if not coupon_code:
        return
    with transaction.atomic():
        updated = (
            _coupon_qs(coupon_code)
            .filter(uses_count__gt=0)
            .update(uses_count=F('uses_count') - 1)
        )
    if updated:
        logger.info('Cupón %s: uses_count decrementado', coupon_code.upper())
    else:
        logger.warning('Cupón %s: no se pudo decrementar uses_count (ya en 0 o no encontrado)', coupon_code.upper())


def _coupon_qs(coupon_code: str):
    from orders.models import Coupon
    return Coupon.objects.select_for_update().filter(
        code=coupon_code.upper(),
        is_active=True,
    )
