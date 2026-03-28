"""
Señales de fidelidad.

Detecta cuando una orden pasa a estado 'cancelled' o 'refunded'
y encola el reverso de puntos.

Los hooks de ACUMULACIÓN (earn) están en:
  - orders/signals.py  (Neki VERIFIED)
  - payments/views.py  (Stripe webhook succeeded)
"""
import logging

from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)

_REVERSAL_STATUSES = frozenset({'cancelled', 'refunded'})


@receiver(pre_save, sender='orders.Order')
def _loyalty_remember_order_status(sender, instance, **kwargs):
    """Guarda el status previo de la orden para detectar la transición."""
    if not instance.pk:
        instance._loyalty_status_prev = None
        return
    try:
        from orders.models import Order
        prev = Order.objects.only('status').get(pk=instance.pk)
        instance._loyalty_status_prev = prev.status
    except Exception:
        instance._loyalty_status_prev = None


@receiver(post_save, sender='orders.Order')
def _loyalty_trigger_reversal_on_cancel(sender, instance, created, **kwargs):
    """
    Encola el reverso de puntos cuando la orden pasa a cancelada/reembolsada.
    Solo actúa en transiciones (prev_status → nuevo_status).
    """
    if created:
        return
    if instance.status not in _REVERSAL_STATUSES:
        return
    prev = getattr(instance, '_loyalty_status_prev', None)
    if prev == instance.status:
        return  # sin cambio real de estado, evitar re-encolar

    from loyalty.tasks import reverse_loyalty_points
    reverse_loyalty_points.delay(str(instance.pk))
    logger.info(
        'Encolado reverso de puntos para orden %s (status=%s).',
        instance.order_number, instance.status,
    )
