"""
Adaptador orientado a Dropi (y APIs similares): productos con id externo + cantidad.

Ajustar `orders_path` y claves de credenciales según la documentación vigente del proveedor.
Las credenciales suelen incluir api_key o token de integración.
"""
from __future__ import annotations

from .rest_generico import RestGenericoAdapter


class DropiAdapter(RestGenericoAdapter):
    """
    Ejemplo de variante sobre REST: payload distinto al genérico.
    La URL por defecto sigue siendo {endpoint_base}/orders/ — sobrescribir si Dropi expone otra ruta.
    """

    def orders_url(self, proveedor) -> str:
        cred = proveedor.credenciales
        suffix = (cred.get('orders_path') or '/orders/').strip()
        if not suffix.startswith('/'):
            suffix = '/' + suffix
        base = (proveedor.endpoint_base or '').rstrip('/')
        return f'{base}{suffix}'

    def construir_payload_pedido(self, pedido_proveedor, lineas: list[dict]) -> dict:
        pedido = pedido_proveedor.local_order
        productos = [
            {
                'external_id': ln['proveedor_variant_id'],
                'sku': ln['sku_proveedor'],
                'quantity': ln['cantidad'],
            }
            for ln in lineas
        ]
        return {
            'external_order_id': str(pedido.order_number),
            'customer': {
                'full_name': pedido.shipping_full_name,
                'email': pedido.email,
                'phone': pedido.shipping_phone,
            },
            'shipping_address': {
                'address': pedido.shipping_address_line1,
                'city': pedido.shipping_city,
                'state': pedido.shipping_department,
                'country': pedido.shipping_country or 'Colombia',
            },
            'products': productos,
            'notes': pedido.customer_notes or '',
        }
