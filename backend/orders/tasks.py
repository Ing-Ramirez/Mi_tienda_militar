"""
Tareas Celery — pedidos (envío a proveedores tras pago verificado).
"""
from __future__ import annotations

import logging

from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=90,
    name='orders.send_order_to_provider',
)
def send_order_to_provider(self, order_id: str) -> None:
    """
    Despacha la orden a proveedores dropshipping (PedidoProveedor + cola enviar_pedido).

    Solo debe ejecutarse cuando el pago manual está VERIFIED; la tarea vuelve a
    comprobarlo por seguridad.
    """
    from orders.models import ManualPaymentStatus, Order
    from proveedores.services.despacho import despachar_orden_a_proveedores

    try:
        order = Order.objects.get(pk=order_id)
    except Order.DoesNotExist:
        logger.error('send_order_to_provider: orden %s no existe', order_id)
        return

    if order.manual_payment_status != ManualPaymentStatus.VERIFIED:
        logger.warning(
            'send_order_to_provider: orden %s no verificada (estado=%s), abortando',
            order_id,
            order.manual_payment_status,
        )
        return

    try:
        despachar_orden_a_proveedores(order)
        logger.info('Despacho a proveedores completado para orden %s', order_id)
    except Exception as exc:
        logger.exception('Error despachando orden %s: %s', order_id, exc)
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))
