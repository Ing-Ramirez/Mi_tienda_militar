"""
Señales de pedidos: encolar envío a proveedores al verificar pago manual (Neki).
"""
from __future__ import annotations

import logging

from django.db import transaction
from django.db.models import F
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
    """Descuenta stock de cada producto/variante al verificar el pago."""
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
                sbs[item.talla] = max(0, current - qty)
                prod.stock_by_size = sbs
                prod.stock = sum(int(v) for v in sbs.values() if v)
            else:
                prod.stock = max(0, prod.stock - qty)

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


@receiver(pre_save, sender=Order)
def _order_remember_status(sender, instance: Order, **kwargs):
    """Guarda status previo para detectar transición a cancelado/reembolsado."""
    if not instance.pk:
        instance._order_status_prev = None
        return
    try:
        prev = Order.objects.only('status').get(pk=instance.pk)
        instance._order_status_prev = prev.status
    except Order.DoesNotExist:
        instance._order_status_prev = None


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


@receiver(pre_save, sender=Order)
def _order_remember_manual_payment_status(sender, instance: Order, **kwargs):
    if not instance.pk:
        instance._manual_payment_prev = None
        return
    try:
        prev = Order.objects.only('manual_payment_status').get(pk=instance.pk)
        instance._manual_payment_prev = prev.manual_payment_status
    except Order.DoesNotExist:
        instance._manual_payment_prev = None


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

    Order.objects.filter(pk=instance.pk, payment_status='pending').update(
        payment_status='paid',
        status='processing',
    )

    # Descontar stock de los productos de la orden
    try:
        _descontar_stock_orden(instance)
    except Exception:
        logger.exception('Error descontando stock para orden %s', instance.order_number)

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
