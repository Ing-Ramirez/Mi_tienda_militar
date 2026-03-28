"""
Servicio de Tracking

Responsabilidades:
  - Crear o actualizar registros de SupplierTracking a partir de webhooks.
  - Mantener el historial cronológico de eventos de envío.
  - Registrar cada actualización en SupplierLog.

Regla: cada evento nuevo se AGREGA al historial — nunca se reemplaza.
"""
import logging

from django.utils import timezone

from ..models import (
    SupplierOrder, SupplierTracking, SupplierLog, EventType,
)

logger = logging.getLogger(__name__)


class ServicioTracking:

    def actualizar_desde_webhook(self, datos: dict, proveedor):
        """
        Actualiza o crea el registro de tracking para un pedido.
        El evento se agrega al historial — el historial es inmutable hacia atrás.
        """
        proveedor_order_id = str(datos.get('order_id', ''))

        try:
            pedido = SupplierOrder.objects.get(
                supplier          = proveedor,
                supplier_order_id = proveedor_order_id,
            )
        except SupplierOrder.DoesNotExist:
            logger.warning(
                f'[{proveedor.name}] Tracking recibido para pedido desconocido: {proveedor_order_id}'
            )
            return

        # Construir el nuevo evento a agregar al historial
        nuevo_evento = {
            'fecha':       timezone.now().isoformat(),
            'estado':      datos.get('status', ''),
            'descripcion': datos.get('description', datos.get('message', '')),
            'ubicacion':   datos.get('location', ''),
        }

        tracking, recien_creado = SupplierTracking.objects.get_or_create(
            order=pedido,
            defaults={
                'supplier_tracking_id': str(datos.get('tracking_id', '')),
                'tracking_number':      datos.get('tracking_number', ''),
                'carrier':              datos.get('carrier', ''),
                'tracking_url':         datos.get('tracking_url', ''),
                'shipping_status':      datos.get('status', ''),
                'events_history':       [nuevo_evento],
            },
        )

        if not recien_creado:
            # Agregar evento al historial existente (sin perder los anteriores)
            tracking.events_history  = tracking.events_history + [nuevo_evento]
            tracking.shipping_status = datos.get('status', tracking.shipping_status)
            tracking.tracking_number = datos.get('tracking_number', tracking.tracking_number)
            tracking.carrier         = datos.get('carrier', tracking.carrier)
            tracking.tracking_url    = datos.get('tracking_url', tracking.tracking_url)
            tracking.save(update_fields=[
                'events_history', 'shipping_status', 'tracking_number',
                'carrier', 'tracking_url', 'updated_at',
            ])

        SupplierLog.objects.create(
            supplier    = proveedor,
            event_type  = EventType.TRACKING_UPDATE,
            payload     = datos,
            status      = 'ok',
            message     = f'Guía {tracking.tracking_number} — {tracking.shipping_status}',
        )
