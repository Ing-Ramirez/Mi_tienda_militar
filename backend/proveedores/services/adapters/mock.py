"""
Adaptador mock: simula recepción de pedido sin red (pruebas y proveedor demo).
"""
from __future__ import annotations

import logging
import uuid

from .base import BaseProveedorAdapter
from .rest_generico import RestGenericoAdapter

logger = logging.getLogger(__name__)


class MockProveedorAdapter(BaseProveedorAdapter):
    """Respuesta exitosa determinista sin HTTP."""

    def enviar_pedido(self, proveedor, payload: dict) -> dict:
        oid = f'MOCK-{uuid.uuid4().hex[:12].upper()}'
        logger.info(
            '[mock] Pedido simulado proveedor=%s referencia=%s',
            proveedor.slug,
            payload.get('referencia_interna') or payload.get('external_order_id'),
        )
        return {'order_id': oid, 'mock': True, 'status': 'accepted'}

    def construir_payload_pedido(self, pedido_proveedor, lineas: list[dict]) -> dict:
        return RestGenericoAdapter().construir_payload_pedido(pedido_proveedor, lineas)
