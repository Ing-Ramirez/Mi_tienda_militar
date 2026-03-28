"""
Servicio de Sincronización

Responsabilidades:
  - Procesar webhooks entrantes en tiempo real.
  - Ejecutar polling completo como fallback (para proveedores sin webhook).
  - Actualizar stock, precio y datos de producto en la DB interna.
  - Registrar cada operación en SupplierLog.

Reglas:
  - La DB interna es la fuente de verdad — el proveedor nunca escribe directamente.
  - Un error de sincronización no detiene el flujo general.
  - Cada cambio queda auditado en SupplierLog.
"""
import logging

from django.utils import timezone

from ..http import proveedor_session
from ..models import (
    SupplierProduct, SupplierVariant,
    SupplierOrder, SupplierOrderStatus,
    SupplierLog, EventType, VariantStatus,
)
from .normalizacion import ServicioNormalizacion

logger = logging.getLogger(__name__)


class ServicioSincronizacion:

    def __init__(self, proveedor):
        self.proveedor    = proveedor
        self.normalizador = ServicioNormalizacion()

    # ── Punto de entrada para webhooks ──────────────────────────────────

    def sincronizar_desde_webhook(self, tipo_evento: str, datos: dict):
        """
        Despacha el webhook al handler correspondiente según el tipo de evento.
        Los tipos de evento aceptados son los definidos por cada proveedor;
        el sistema mapea los más comunes a handlers internos.
        """
        handlers = {
            # Producto
            'product.created':  self._crear_o_actualizar_producto,
            'product.updated':  self._crear_o_actualizar_producto,
            # Stock
            'stock.updated':    self._actualizar_stock,
            'inventory.update': self._actualizar_stock,
            # Precio
            'price.updated':    self._actualizar_precio,
            # Pedido
            'order.updated':    self._actualizar_pedido,
            'order.shipped':    self._actualizar_pedido,
            'order.cancelled':  self._actualizar_pedido,
            # Tracking
            'tracking.updated': self._actualizar_tracking,
            'shipment.update':  self._actualizar_tracking,
        }
        handler = handlers.get(tipo_evento)
        if handler:
            try:
                handler(datos)
            except Exception as exc:
                logger.error(
                    f'[{self.proveedor.name}] Error procesando "{tipo_evento}": {exc}',
                    exc_info=True,
                )
                SupplierLog.objects.create(
                    supplier=self.proveedor,
                    event_type=EventType.ERROR,
                    payload=datos,
                    status='error',
                    message=str(exc),
                )
        else:
            logger.warning(
                f'[{self.proveedor.name}] Evento desconocido: "{tipo_evento}"'
            )

    # ── Handlers internos ───────────────────────────────────────────────

    def _actualizar_stock(self, datos: dict):
        """
        Actualiza el stock de una variante específica.
        Después de actualizar, dispara el motor de stock dinámico para
        recalcular el stock visible en todos los LinkedProduct asociados.
        """
        variant_id   = str(datos.get('variant_id') or datos.get('sku', ''))
        stock_raw    = int(datos.get('stock') or datos.get('quantity', 0))
        stock_ajust  = max(0, stock_raw - self.proveedor.stock_buffer)
        nuevo_estado = VariantStatus.ACTIVO if stock_ajust > 0 else VariantStatus.AGOTADO

        variantes_actualizadas = SupplierVariant.objects.filter(
            supplier_product__supplier=self.proveedor,
            supplier_variant_id=variant_id,
        )
        count = variantes_actualizadas.update(
            stock=stock_ajust, status=nuevo_estado, updated_at=timezone.now(),
        )

        SupplierLog.objects.create(
            supplier    = self.proveedor,
            event_type  = EventType.SYNC_STOCK,
            payload     = datos,
            status      = 'ok' if count else 'error',
            message     = f'Stock variante {variant_id}: {stock_ajust} uds. (estado: {nuevo_estado})',
        )

        # ── Propagar al catálogo local vía motor de stock dinámico ──
        if count:
            from .stock_dinamico import ServicioStockDinamico
            for variante in SupplierVariant.objects.filter(
                supplier_product__supplier=self.proveedor,
                supplier_variant_id=variant_id,
            ):
                ServicioStockDinamico().propagar_desde_variante(variante)

    def _actualizar_precio(self, datos: dict):
        """Recalcula base_price y calculated_price de una variante."""
        variant_id = str(datos.get('variant_id') or datos.get('sku', ''))
        try:
            variante = SupplierVariant.objects.get(
                supplier_product__supplier=self.proveedor,
                supplier_variant_id=variant_id,
            )
        except SupplierVariant.DoesNotExist:
            logger.warning(f'Variante {variant_id} no encontrada para actualizar precio.')
            return

        datos_norm = self.normalizador.normalizar_variante(datos, self.proveedor)
        variante.base_price       = datos_norm['base_price']
        variante.calculated_price = datos_norm['calculated_price']
        variante.save(update_fields=['base_price', 'calculated_price', 'updated_at'])

        SupplierLog.objects.create(
            supplier    = self.proveedor,
            event_type  = EventType.SYNC_PRECIO,
            payload     = datos,
            status      = 'ok',
            message     = f'Precio variante {variante.sku}: base={variante.base_price}, calculado={variante.calculated_price}',
        )

    def _crear_o_actualizar_producto(self, datos: dict):
        """Crea o actualiza un producto y todas sus variantes."""
        datos_norm = self.normalizador.normalizar_producto(datos, self.proveedor)

        producto, creado = SupplierProduct.objects.update_or_create(
            supplier            = self.proveedor,
            supplier_product_id = datos_norm['supplier_product_id'],
            defaults={
                'name':          datos_norm['name'],
                'description':   datos_norm['description'],
                'category_name': datos_norm['category_name'],
                'raw_data':      datos_norm['raw_data'],
            },
        )

        # Sincronizar variantes incluidas en el payload
        for variante_raw in datos.get('variants', []):
            v_norm = self.normalizador.normalizar_variante(variante_raw, self.proveedor)
            SupplierVariant.objects.update_or_create(
                supplier_product    = producto,
                supplier_variant_id = v_norm['supplier_variant_id'],
                defaults=v_norm,
            )

        SupplierLog.objects.create(
            supplier    = self.proveedor,
            event_type  = EventType.SYNC_PRODUCTO,
            payload     = {'product_id': datos_norm['supplier_product_id']},
            status      = 'ok',
            message     = f'{"Creado" if creado else "Actualizado"}: {datos_norm["name"]}',
        )

        # Propagar stock a vínculos existentes para todas las variantes del producto
        from .stock_dinamico import ServicioStockDinamico
        motor = ServicioStockDinamico()
        for variante in producto.variantes.filter(status='activo'):
            motor.propagar_desde_variante(variante)

    def _actualizar_pedido(self, datos: dict):
        """Actualiza el estado de un SupplierOrder a partir de un webhook."""
        proveedor_order_id = str(datos.get('order_id', ''))
        nuevo_estado       = self._mapear_estado_pedido(datos.get('status', ''))

        SupplierOrder.objects.filter(
            supplier          = self.proveedor,
            supplier_order_id = proveedor_order_id,
        ).update(status=nuevo_estado, supplier_response=datos)

    def _actualizar_tracking(self, datos: dict):
        from .tracking import ServicioTracking
        ServicioTracking().actualizar_desde_webhook(datos, self.proveedor)

    # ── Polling de respaldo ─────────────────────────────────────────────

    def polling_completo(self):
        """
        Sincronización completa del catálogo desde la API del proveedor.
        Actúa como fallback cuando no hay webhooks disponibles.
        """
        if self.proveedor.integration_type == 'api_rest':
            self._polling_api_rest()
        elif self.proveedor.integration_type == 'csv':
            logger.info(f'[{self.proveedor.name}] Polling CSV: no implementado aún.')
        else:
            logger.debug(f'[{self.proveedor.name}] Sin polling para tipo: {self.proveedor.integration_type}')

    def _polling_api_rest(self):
        """Descarga el catálogo completo vía API REST y sincroniza producto por producto."""
        if not self.proveedor.endpoint_base:
            return
        credenciales = self.proveedor.credenciales or {}
        api_key = credenciales.get('api_key') or credenciales.get('token', '')
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type':  'application/json',
        }

        # Soportar endpoint con y sin slash final, y sin "/products" si ya viene en endpoint_base
        base = self.proveedor.endpoint_base.rstrip('/')
        url  = f'{base}/products'

        try:
            resp = proveedor_session().get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            # Soportar: lista plana | {"products": [...]} | {"result": [...]} (Printful)
            if isinstance(data, list):
                productos = data
            else:
                productos = (
                    data.get('result') or
                    data.get('products') or
                    data.get('items') or
                    []
                )

            for product_raw in productos:
                try:
                    self._crear_o_actualizar_producto(product_raw)
                except Exception as exc:
                    logger.error(f'Error procesando producto en polling: {exc}')

        except Exception as exc:
            SupplierLog.objects.create(
                supplier    = self.proveedor,
                event_type  = EventType.ERROR,
                status      = 'error',
                message     = f'Error en polling REST: {exc}',
            )
            raise

    # ── Helpers privados ────────────────────────────────────────────────

    def _mapear_estado_pedido(self, estado_externo: str) -> str:
        mapa = {
            'confirmed':  SupplierOrderStatus.CONFIRMADO,
            'processing': SupplierOrderStatus.CONFIRMADO,
            'shipped':    SupplierOrderStatus.EN_TRANSITO,
            'delivered':  SupplierOrderStatus.ENTREGADO,
            'cancelled':  SupplierOrderStatus.CANCELADO,
            'canceled':   SupplierOrderStatus.CANCELADO,
        }
        if estado_externo is None:
            return SupplierOrderStatus.CONFIRMADO
        clave = str(estado_externo).strip().lower()
        return mapa.get(clave, SupplierOrderStatus.CONFIRMADO)
