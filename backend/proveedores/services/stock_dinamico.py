"""
Servicio de Stock Dinámico — Motor central de "capped stock sync"

Fórmula única e inmutable:
    stock_visible = min(stock_proveedor, max_stock)

Responsabilidades:
  - Recalcular el stock visible de un LinkedProduct.
  - Propagar el resultado al products.Product del catálogo.
  - Garantizar que NUNCA se muestre más stock del límite configurado.
  - Nunca descender por debajo de 0.

Reglas de propagación:
  - Si el producto usa tallas (requires_size=True): actualiza stock_by_size.
  - Si no usa tallas: actualiza el campo stock global.
  - Solo propaga si vinculo.sync_enabled=True y vinculo.is_active=True.
"""
import logging

from django.utils import timezone

logger = logging.getLogger(__name__)


class ServicioStockDinamico:

    # ── API pública ──────────────────────────────────────────────────────

    def propagar_desde_variante(self, variante_proveedor):
        """
        Punto de entrada principal.
        Llamado por ServicioSincronizacion cada vez que cambia el stock
        de una SupplierVariant (webhook o polling).

        Encuentra todos los vínculos activos y sincronizables de esa variante
        y recalcula el stock en el catálogo local.
        """
        from ..models import LinkedProduct

        vinculos = LinkedProduct.objects.filter(
            supplier_variant = variante_proveedor,
            is_active        = True,
            sync_enabled     = True,
        ).select_related('supplier_variant', 'local_product')

        for vinculo in vinculos:
            try:
                self.recalcular(vinculo)
            except Exception as exc:
                logger.error(
                    f'Error propagando stock para vínculo {vinculo.id}: {exc}',
                    exc_info=True,
                )

    def recalcular(self, vinculo):
        """
        Recalcula el stock_visible para un vínculo específico y lo propaga al catálogo.

        stock_visible = min(stock_proveedor, max_stock)   → siempre ≥ 0

        Actualiza:
          - vinculo.calculated_stock (caché)
          - local_product.stock  (o stock_by_size si usa tallas)
        """
        stock_proveedor = vinculo.supplier_variant.stock
        stock_maximo    = vinculo.max_stock
        stock_visible   = max(0, min(stock_proveedor, stock_maximo))

        # 1. Guardar en caché del vínculo
        vinculo.calculated_stock     = stock_visible
        vinculo.last_recalculated_at = timezone.now()
        vinculo.save(update_fields=['calculated_stock', 'last_recalculated_at'])

        # 2. Propagar al producto del catálogo
        producto = vinculo.local_product
        self._propagar_a_producto(producto, stock_visible, vinculo.supplier_variant)

        logger.info(
            f'Stock recalculado: {vinculo.supplier_variant.sku} → '
            f'{producto.name} | proveedor={stock_proveedor} máx={stock_maximo} visible={stock_visible}'
        )

    def recalcular_todos(self):
        """
        Recalcula el stock de TODOS los vínculos activos.
        Usado por la tarea periódica de Celery para garantizar consistencia.
        """
        from ..models import LinkedProduct

        vinculos = LinkedProduct.objects.filter(
            is_active=True, sync_enabled=True,
        ).select_related('supplier_variant', 'local_product')

        actualizados = 0
        errores = 0

        for vinculo in vinculos:
            try:
                self.recalcular(vinculo)
                actualizados += 1
            except Exception as exc:
                logger.error(f'Error en recalcular_todos para vínculo {vinculo.id}: {exc}')
                errores += 1

        logger.info(f'recalcular_todos: {actualizados} OK, {errores} errores')
        return actualizados, errores

    # ── Propagación al catálogo ──────────────────────────────────────────

    def _propagar_a_producto(self, producto, stock_visible: int, variante_proveedor):
        """
        Escribe el stock calculado en el producto del catálogo.

        Si el producto usa tallas (requires_size=True):
          - Actualiza solo la talla correspondiente a los atributos de la variante.
          - Recalcula el stock total como suma de todas las tallas.

        Si el producto NO usa tallas:
          - Actualiza directamente el campo stock global.
        """
        if producto.requires_size:
            self._propagar_con_tallas(producto, stock_visible, variante_proveedor)
        else:
            self._propagar_sin_tallas(producto, stock_visible)

    def _propagar_sin_tallas(self, producto, stock_visible: int):
        producto.stock = stock_visible
        producto.save(update_fields=['stock'])

    def _propagar_con_tallas(self, producto, stock_visible: int, variante_proveedor):
        """
        Actualiza la talla específica dentro de stock_by_size.
        La talla se obtiene de los atributos de la variante del proveedor.
        """
        atributos = variante_proveedor.attributes or {}
        talla = (
            atributos.get('talla')
            or atributos.get('size')
            or atributos.get('talla_proveedor', '')
        )

        if not talla:
            # Sin talla definida → actualizar stock global como fallback
            self._propagar_sin_tallas(producto, stock_visible)
            return

        # Clonar el dict actual para no mutar el original
        stock_by_size = dict(producto.stock_by_size or {})
        stock_by_size[talla] = stock_visible

        # Recalcular stock total como suma de todas las tallas
        stock_total = sum(max(0, v) for v in stock_by_size.values())

        producto.stock_by_size      = stock_by_size
        producto.stock              = stock_total
        producto.available_sizes    = [t for t, s in stock_by_size.items() if s > 0]
        producto.save(update_fields=['stock_by_size', 'stock', 'available_sizes'])
