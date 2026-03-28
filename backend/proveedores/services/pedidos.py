"""
Servicio de Pedidos

Responsabilidades:
  - Crear el SupplierOrder interno antes de enviar al proveedor.
  - Construir el payload según el adaptador del proveedor.
  - Enviar el pedido vía API con manejo de errores.
  - Actualizar el estado y guardar la respuesta para auditoría.

Reglas:
  - Máximo 3 intentos (los reintentos los gestiona Celery con backoff exponencial).
  - Un fallo en el envío NO cancela el pedido local — cambia el estado a error_proveedor.
  - Todo intento queda registrado en SupplierLog.
"""
import logging

from ..models import (
    SupplierOrder, SupplierOrderStatus, SupplierLog, EventType,
)
from .adapters import get_adapter
from .vinculos import resolver_vinculo_para_order_item

logger = logging.getLogger(__name__)


def _proveedor_order_id_desde_respuesta(resp: dict) -> str:
    if not resp:
        return ''
    for key in ('order_id', 'id', 'orderId'):
        if resp.get(key) is not None:
            return str(resp[key])
    data = resp.get('data')
    if isinstance(data, dict):
        for key in ('order_id', 'id', 'orderId'):
            if data.get(key) is not None:
                return str(data[key])
    return ''


class ServicioPedidos:
    MAX_INTENTOS = 3

    # ── Creación ────────────────────────────────────────────────────────

    def crear_pedido_proveedor(
        self,
        pedido_local,
        proveedor,
        total=None,
    ) -> SupplierOrder:
        """
        Registra el pedido internamente con estado pendiente_envio.
        Debe llamarse ANTES de encolar el envío asíncrono.

        total:
            Suma de line_total de ítenes de este proveedor; por defecto el total de la orden local.
        """
        return SupplierOrder.objects.create(
            supplier=proveedor,
            local_order=pedido_local,
            status=SupplierOrderStatus.PENDIENTE_ENVIO,
            total=pedido_local.total if total is None else total,
            currency='COP',
        )

    # ── Líneas vinculadas al proveedor ──────────────────────────────────

    def lineas_para_proveedor(self, pedido_proveedor: SupplierOrder) -> list[dict]:
        """Ítems de la orden cuyo vínculo apunta a este proveedor."""
        prov_id = pedido_proveedor.supplier_id
        out: list[dict] = []
        qs = pedido_proveedor.local_order.items.select_related('product', 'variant')
        for item in qs.all():
            if not item.product_id:
                continue
            v = resolver_vinculo_para_order_item(item)
            if not v or v.supplier_variant.supplier_product.supplier_id != prov_id:
                continue
            vp = v.supplier_variant
            out.append(
                {
                    'orden_item_id': str(item.id),
                    'proveedor_variant_id': vp.supplier_variant_id,
                    'sku_proveedor': vp.sku,
                    'cantidad': item.quantity,
                    'precio_unit': str(item.unit_price),
                    'nombre': item.product_name,
                    'bordado': item.bordado or '',
                    'rh': item.rh or '',
                    'talla': item.talla or '',
                }
            )
        return out

    # ── Envío ───────────────────────────────────────────────────────────

    def enviar_a_proveedor(self, pedido_proveedor: SupplierOrder) -> bool:
        """
        Construye el payload y lo envía al proveedor.
        Retorna True si el envío fue exitoso, False si falló.
        El estado del SupplierOrder se actualiza en ambos casos.
        """
        lineas = self.lineas_para_proveedor(pedido_proveedor)
        if not lineas:
            logger.error(
                'SupplierOrder %s sin líneas mapeadas al proveedor — abortando envío',
                pedido_proveedor.id,
            )
            return False

        adapter = get_adapter(pedido_proveedor.supplier)
        payload = adapter.construir_payload_pedido(pedido_proveedor, lineas)

        pedido_proveedor.sent_payload = payload
        pedido_proveedor.attempts += 1
        pedido_proveedor.save(update_fields=['sent_payload', 'attempts'])

        try:
            respuesta = adapter.enviar_pedido(pedido_proveedor.supplier, payload)
            ext_id = _proveedor_order_id_desde_respuesta(respuesta)

            pedido_proveedor.supplier_order_id = ext_id
            pedido_proveedor.supplier_response = respuesta
            pedido_proveedor.status = SupplierOrderStatus.ENVIADO
            pedido_proveedor.save(
                update_fields=['supplier_order_id', 'supplier_response', 'status']
            )

            SupplierLog.objects.create(
                supplier=pedido_proveedor.supplier,
                event_type=EventType.PEDIDO_ENVIADO,
                payload=payload,
                response=respuesta,
                status='ok',
                message=(
                    f'Pedido #{pedido_proveedor.local_order.order_number} '
                    f'enviado exitosamente.'
                ),
            )
            return True

        except Exception as exc:
            pedido_proveedor.status = SupplierOrderStatus.ERROR_PROVEEDOR
            pedido_proveedor.save(update_fields=['status'])

            SupplierLog.objects.create(
                supplier=pedido_proveedor.supplier,
                event_type=EventType.PEDIDO_ERROR,
                payload=payload,
                response={'error': str(exc)},
                status='error',
                message=str(exc),
            )
            logger.error(
                'Error enviando pedido %s (intento %s): %s',
                pedido_proveedor.id,
                pedido_proveedor.attempts,
                exc,
                exc_info=True,
            )
            return False
