"""
Proveedores — Tareas Celery

Tareas asíncronas con reintentos automáticos y backoff exponencial.

  procesar_webhook          → procesamiento asíncrono de webhooks entrantes
  enviar_pedido_a_proveedor → envío de pedidos con hasta 3 reintentos
  sincronizacion_periodica  → polling de catálogos (fallback para proveedores sin webhook)
"""
import logging

from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name='proveedores.procesar_webhook',
)
def procesar_webhook(self, proveedor_id: str, tipo_evento: str, datos: dict, log_id=None):
    """
    Procesa un webhook entrante de forma asíncrona.
    Se encola inmediatamente después de responder 200 al proveedor.

    Reintentos: hasta 3 veces con backoff exponencial (30s → 60s → 120s).
    """
    from .models import Supplier
    from .services.sincronizacion import ServicioSincronizacion

    try:
        proveedor = Supplier.objects.get(id=proveedor_id)
        ServicioSincronizacion(proveedor).sincronizar_desde_webhook(tipo_evento, datos)
        logger.info(f'Webhook procesado: [{tipo_evento}] proveedor={proveedor.name}')
    except Exception as exc:
        logger.error(f'Error procesando webhook [{tipo_evento}]: {exc}')
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=120,
    name='proveedores.enviar_pedido',
)
def enviar_pedido_a_proveedor(self, pedido_proveedor_id: str):
    """
    Envía un pedido al proveedor con reintentos automáticos.

    Reintentos: hasta 3 veces con backoff exponencial (60s → 120s → 240s).
    Si agota los reintentos, el pedido queda en estado error_proveedor
    y queda registrado en SupplierLog para gestión manual.
    """
    from .models import SupplierOrder
    from .services.pedidos import ServicioPedidos

    try:
        pedido = SupplierOrder.objects.get(id=pedido_proveedor_id)

        if pedido.attempts >= ServicioPedidos.MAX_INTENTOS:
            logger.error(
                f'Pedido {pedido_proveedor_id} alcanzó el máximo de intentos '
                f'({ServicioPedidos.MAX_INTENTOS}). Intervención manual requerida.'
            )
            return

        exito = ServicioPedidos().enviar_a_proveedor(pedido)

        if not exito:
            raise Exception(f'Fallo en intento {pedido.attempts}')

        logger.info(f'Pedido {pedido_proveedor_id} enviado exitosamente.')

    except Exception as exc:
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 60)


@shared_task(name='proveedores.sincronizacion_periodica')
def sincronizacion_periodica():
    """
    Sincronización periódica del catálogo de todos los proveedores activos con API REST o CSV.
    Ejecutada por Celery Beat cada 30 minutos como fallback para proveedores sin webhook.
    """
    from .models import Supplier
    from .services.sincronizacion import ServicioSincronizacion

    proveedores = Supplier.objects.filter(
        status           = 'activo',
        integration_type__in = ['api_rest', 'csv'],
    )

    for proveedor in proveedores:
        try:
            ServicioSincronizacion(proveedor).polling_completo()
            logger.info(f'Polling completado: {proveedor.name}')
        except Exception as exc:
            logger.error(f'Error en polling de {proveedor.name}: {exc}')
            # No relanzar — continuar con el siguiente proveedor
