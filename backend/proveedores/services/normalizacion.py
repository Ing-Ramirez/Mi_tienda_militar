"""
Servicio de Normalización

Transforma datos crudos del proveedor al esquema interno.
NUNCA se deben persistir datos externos sin pasar por aquí.

Responsabilidades:
  - Mapear campos del proveedor a nombres internos.
  - Calcular calculated_price aplicando la política de precios.
  - Aplicar buffer de stock.
  - Validar coherencia antes de retornar.
"""
from decimal import Decimal, ROUND_HALF_UP


class ServicioNormalizacion:

    # ── Producto ────────────────────────────────────────────────────────

    def normalizar_producto(self, datos_raw: dict, proveedor) -> dict:
        """
        Mapea un dict del proveedor al esquema de SupplierProduct.
        Retorna solo los campos necesarios para crear/actualizar el registro.
        """
        return {
            'supplier_product_id': str(
                datos_raw.get('id')
                or datos_raw.get('product_id')
                or datos_raw.get('sku', '')
            ),
            'name': (
                datos_raw.get('title')
                or datos_raw.get('name')
                or datos_raw.get('nombre', '')
            ),
            'description':   datos_raw.get('description') or datos_raw.get('descripcion', ''),
            'category_name': datos_raw.get('category') or datos_raw.get('categoria', ''),
            'raw_data':      datos_raw,
        }

    # ── Variante ────────────────────────────────────────────────────────

    def normalizar_variante(self, datos_raw: dict, proveedor) -> dict:
        """
        Mapea un dict de variante al esquema de SupplierVariant.
        Aplica política de precios y buffer de stock.
        """
        base_price        = self._extraer_precio(datos_raw)
        calculated_price  = self._aplicar_politica(base_price, proveedor.pricing_policy)
        stock_ajustado    = self._ajustar_stock(datos_raw, proveedor.stock_buffer)

        return {
            'supplier_variant_id': str(
                datos_raw.get('id')
                or datos_raw.get('variant_id')
                or datos_raw.get('sku', '')
            ),
            'sku':              datos_raw.get('sku', ''),
            'base_price':       base_price,
            'calculated_price': calculated_price,
            'stock':            stock_ajustado,
            'attributes':       self._extraer_atributos(datos_raw),
            'image_url':        datos_raw.get('image') or datos_raw.get('image_url', ''),
        }

    # ── Helpers privados ────────────────────────────────────────────────

    def _extraer_precio(self, datos: dict) -> Decimal:
        raw = (
            datos.get('retail_price')  # Printful
            or datos.get('price')
            or datos.get('precio')
            or datos.get('unit_price', 0)
        )
        try:
            return Decimal(str(raw))
        except Exception:
            return Decimal('0')

    def _ajustar_stock(self, datos: dict, buffer: int) -> int:
        raw = datos.get('stock') or datos.get('quantity') or datos.get('qty', 0)
        try:
            stock_raw = int(raw)
        except (TypeError, ValueError):
            stock_raw = 0
        return max(0, stock_raw - buffer)

    def _extraer_atributos(self, datos: dict) -> dict:
        """
        Extrae atributos de variante en formato {nombre: valor}.
        Soporta tanto formato plano como lista de atributos.
        """
        # Formato plano: {"color": "negro", "talla": "M"}
        atributos_planos = {
            k: datos[k]
            for k in ('color', 'talla', 'size', 'material', 'modelo', 'estilo')
            if k in datos
        }
        if atributos_planos:
            return atributos_planos

        # Formato lista: {"attributes": [{"name": "color", "value": "negro"}]}
        atributos_lista = datos.get('attributes') or datos.get('atributos', [])
        if isinstance(atributos_lista, list):
            return {
                a.get('name', a.get('nombre', '')): a.get('value', a.get('valor', ''))
                for a in atributos_lista
                if isinstance(a, dict)
            }

        return {}

    def _aplicar_politica(self, base_price: Decimal, politica: dict) -> Decimal:
        """
        Calcula calculated_price según la política configurada en el proveedor.

        Tipos soportados:
          margen       → base_price * (1 + valor)   — ej: valor=0.30 sube 30%
          multiplicador → base_price * valor
          fijo          → base_price + valor
        """
        tipo  = politica.get('tipo', 'margen')
        valor = Decimal(str(politica.get('valor', '0')))

        if tipo == 'margen':
            resultado = base_price * (Decimal('1') + valor)
        elif tipo == 'multiplicador':
            resultado = base_price * valor
        elif tipo == 'fijo':
            resultado = base_price + valor
        else:
            resultado = base_price

        # Redondea al peso colombiano más cercano (sin centavos)
        return resultado.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
