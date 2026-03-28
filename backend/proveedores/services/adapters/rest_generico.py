"""
Adaptador REST genérico: Bearer token desde credenciales.api_key, JSON en POST …/orders/.
Compatible con el comportamiento previo de ServicioPedidos._llamar_api_proveedor.
"""
from __future__ import annotations

import logging

from .base import BaseProveedorAdapter
from ...http import proveedor_session

logger = logging.getLogger(__name__)


class RestGenericoAdapter(BaseProveedorAdapter):
    TIMEOUT_SEGUNDOS = 30

    def orders_url(self, proveedor) -> str:
        base = (proveedor.endpoint_base or '').rstrip('/')
        return f'{base}/orders/'

    def auth_headers(self, proveedor) -> dict[str, str]:
        cred = proveedor.credenciales
        token = cred.get('api_key') or cred.get('token') or ''
        return {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}',
        }

    def enviar_pedido(self, proveedor, payload: dict) -> dict:
        resp = proveedor_session().post(
            self.orders_url(proveedor),
            json=payload,
            headers=self.auth_headers(proveedor),
            timeout=self.TIMEOUT_SEGUNDOS,
        )
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    def construir_payload_pedido(self, pedido_proveedor, lineas: list[dict]) -> dict:
        pedido = pedido_proveedor.local_order
        articulos = []
        for ln in lineas:
            articulos.append(
                {
                    'sku': ln['sku_proveedor'],
                    'proveedor_variant_id': ln['proveedor_variant_id'],
                    'cantidad': ln['cantidad'],
                    'precio_unit': ln['precio_unit'],
                    'nombre': ln.get('nombre') or '',
                    'bordado': ln.get('bordado') or '',
                    'rh': ln.get('rh') or '',
                    'talla': ln.get('talla') or '',
                }
            )
        return {
            'referencia_interna': str(pedido.order_number),
            'cliente': {
                'nombre': pedido.shipping_full_name,
                'email': pedido.email,
                'telefono': pedido.shipping_phone,
            },
            'direccion_envio': {
                'direccion': pedido.shipping_address_line1,
                'ciudad': pedido.shipping_city,
                'departamento': pedido.shipping_department,
            },
            'articulos': articulos,
            'total': str(pedido_proveedor.total),
            'moneda': pedido_proveedor.currency or 'COP',
        }
