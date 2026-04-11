"""
Señales de pedidos: encolar envío a proveedores al verificar pago manual (Neki).
"""
from __future__ import annotations

import logging

from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from orders.models import ManualPaymentStatus, Order

logger = logging.getLogger(__name__)


_CANCEL_STATUSES = frozenset({'cancelled', 'refunded'})


def _restaurar_stock_orden(order: Order) -> None:
    """Devuelve el stock de cada ítem al cancelar/reembolsar una orden.

    Solo aplica si la orden fue verificada (pago confirmado) — evita
    restaurar stock de órdenes que nunca lo descontaron.
    """
    from products.models import InventoryLog, Product, ProductVariant

    if order.manual_payment_status != ManualPaymentStatus.VERIFIED:
        return

    for item in order.items.select_related('product', 'variant').all():
        product = item.product
        if product is None:
            continue

        qty = item.quantity
        with transaction.atomic():
            prod = Product.objects.select_for_update().get(pk=product.pk)
            stock_before = prod.stock

            if prod.requires_size and item.talla:
                sbs = prod.stock_by_size if isinstance(prod.stock_by_size, dict) else {}
                current = int(sbs.get(item.talla, 0))
                sbs[item.talla] = current + qty
                prod.stock_by_size = sbs
                prod.stock = sum(int(v) for v in sbs.values() if v)
            else:
                prod.stock = prod.stock + qty

            prod.save(update_fields=['stock', 'stock_by_size'])
            stock_after = prod.stock

            InventoryLog.objects.create(
                product=prod,
                variant=item.variant,
                action='return',
                quantity_change=qty,
                stock_before=stock_before,
                stock_after=stock_after,
                notes=f'Devolución por cancelación — orden {order.order_number}',
            )

        if item.variant:
            with transaction.atomic():
                var = ProductVariant.objects.select_for_update().get(pk=item.variant.pk)
                var.stock = var.stock + qty
                var.save(update_fields=['stock'])


def _descontar_stock_orden(order: Order) -> None:
    """Descuenta stock de cada producto/variante al verificar el pago.

    Lanza ValueError si el stock actual es insuficiente para algún ítem —
    el llamador debe manejar el error (rollback) para evitar inconsistencias.
    """
    from products.models import InventoryLog, Product, ProductVariant

    for item in order.items.select_related('product', 'variant').all():
        product = item.product
        if product is None:
            continue

        qty = item.quantity
        with transaction.atomic():
            prod = Product.objects.select_for_update().get(pk=product.pk)
            stock_before = prod.stock

            if prod.requires_size and item.talla:
                sbs = prod.stock_by_size if isinstance(prod.stock_by_size, dict) else {}
                current = int(sbs.get(item.talla, 0))
                if current < qty:
                    raise ValueError(
                        f'Stock insuficiente para "{prod.name}" talla {item.talla}: '
                        f'disponible={current}, requerido={qty} '
                        f'(orden {order.order_number}).'
                    )
                sbs[item.talla] = current - qty
                prod.stock_by_size = sbs
                prod.stock = sum(int(v) for v in sbs.values() if v)
            else:
                # stock == 0 en producto sin talla = sin restricción → no descontar
                if prod.stock > 0:
                    if prod.stock < qty:
                        raise ValueError(
                            f'Stock insuficiente para "{prod.name}": '
                            f'disponible={prod.stock}, requerido={qty} '
                            f'(orden {order.order_number}).'
                        )
                    prod.stock = prod.stock - qty

            prod.save(update_fields=['stock', 'stock_by_size'])
            stock_after = prod.stock

            InventoryLog.objects.create(
                product=prod,
                variant=item.variant,
                action='sale',
                quantity_change=-qty,
                stock_before=stock_before,
                stock_after=stock_after,
                notes=f'Venta automática — orden {order.order_number}',
            )

        # Descontar también la variante si aplica
        if item.variant:
            with transaction.atomic():
                var = ProductVariant.objects.select_for_update().get(pk=item.variant.pk)
                var.stock = max(0, var.stock - qty)
                var.save(update_fields=['stock'])


# ── Un solo pre_save que lee ambos estados previos en una query (evita N+1) ─────

@receiver(pre_save, sender=Order)
def _order_remember_previous_states(sender, instance: Order, **kwargs):
    """Guarda status y manual_payment_status previos en una sola query."""
    if not instance.pk:
        instance._order_status_prev = None
        instance._manual_payment_prev = None
        return
    try:
        prev = Order.objects.only('status', 'manual_payment_status').get(pk=instance.pk)
        instance._order_status_prev = prev.status
        instance._manual_payment_prev = prev.manual_payment_status
    except Order.DoesNotExist:
        instance._order_status_prev = None
        instance._manual_payment_prev = None


@receiver(post_save, sender=Order)
def _order_restore_stock_on_cancel(sender, instance: Order, created: bool, **kwargs):
    """Restaura stock cuando la orden pasa a cancelada o reembolsada."""
    if created:
        return
    if instance.status not in _CANCEL_STATUSES:
        return
    prev = getattr(instance, '_order_status_prev', None)
    if prev == instance.status:
        return  # sin cambio real, no actuar
    try:
        _restaurar_stock_orden(instance)
    except Exception:
        logger.exception('Error restaurando stock para orden %s', instance.order_number)
        raise


@receiver(post_save, sender=Order)
def _order_enqueue_dispatch_when_verified(sender, instance: Order, created: bool, **kwargs):
    if created:
        return
    if instance.manual_payment_status != ManualPaymentStatus.VERIFIED:
        return
    prev = getattr(instance, '_manual_payment_prev', None)
    if prev == ManualPaymentStatus.VERIFIED:
        return
    if instance.providers_dispatch_enqueued_at:
        return

    # Actualizar estado de pago + descontar stock en una sola transacción atómica.
    # Si el stock falla, el cambio de estado se revierte también.
    try:
        with transaction.atomic():
            Order.objects.filter(pk=instance.pk, payment_status='pending').update(
                payment_status='paid',
                status='processing',
            )
            _descontar_stock_orden(instance)
    except Exception:
        logger.exception(
            'Error al descontar stock o actualizar estado para orden %s. '
            'Revisión manual requerida.',
            instance.order_number,
        )
        raise

    from orders.tasks import send_order_to_provider

    updated = Order.objects.filter(
        pk=instance.pk,
        providers_dispatch_enqueued_at__isnull=True,
    ).update(providers_dispatch_enqueued_at=timezone.now())
    if updated:
        send_order_to_provider.delay(str(instance.pk))
        logger.info(
            'Encolado send_order_to_provider para orden %s (pago verificado)',
            instance.order_number,
        )

    # Encolar acumulación de puntos de fidelidad (idempotente en el servicio)
    from loyalty.tasks import assign_loyalty_points
    assign_loyalty_points.delay(str(instance.pk))
    logger.info(
        'Encolado assign_loyalty_points para orden %s (pago verificado)',
        instance.order_number,
    )
