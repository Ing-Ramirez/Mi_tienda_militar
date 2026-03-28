"""
Franja Pixelada — Tareas Celery del sistema de fidelidad

assign_loyalty_points   : asigna puntos tras confirmar el pago de una orden.
reverse_loyalty_points  : revierte puntos al cancelar o reembolsar una orden.

Ambas tareas son idempotentes: pueden reintentarse sin duplicar operaciones.
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    name='loyalty.assign_loyalty_points',
)
def assign_loyalty_points(self, order_id: str) -> None:
    """
    Asigna puntos al usuario por una orden con payment_status='paid'.
    Se encola desde el webhook de Stripe y desde la señal de Neki VERIFIED.
    """
    from orders.models import Order
    from loyalty import services

    try:
        order = Order.objects.select_related('user').get(pk=order_id)
    except Order.DoesNotExist:
        logger.error('assign_loyalty_points: orden %s no encontrada.', order_id)
        return

    try:
        services.assign_points_for_order(order)
    except Exception as exc:
        logger.exception(
            'Error asignando puntos para orden %s: %s', order_id, exc,
        )
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(
    bind=True,
    max_retries=3,
    name='loyalty.reverse_loyalty_points',
)
def reverse_loyalty_points(self, order_id: str) -> None:
    """
    Revierte puntos ganados y/o devuelve puntos usados cuando una orden
    es cancelada o reembolsada.
    """
    from orders.models import Order
    from loyalty import services

    try:
        order = Order.objects.select_related('user').get(pk=order_id)
    except Order.DoesNotExist:
        logger.error('reverse_loyalty_points: orden %s no encontrada.', order_id)
        return

    try:
        services.reverse_points_for_order(order)
    except Exception as exc:
        logger.exception(
            'Error revirtiendo puntos para orden %s: %s', order_id, exc,
        )
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
