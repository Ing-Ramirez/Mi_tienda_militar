"""
Señales de pedidos: encolar envío a proveedores al verificar pago manual (Neki).
"""
from __future__ import annotations

import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from orders.models import ManualPaymentStatus, Order

logger = logging.getLogger(__name__)


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
