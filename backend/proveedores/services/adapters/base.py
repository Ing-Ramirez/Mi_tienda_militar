"""
Contrato de adaptadores de proveedor (envío de pedidos, futura sync).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseProveedorAdapter(ABC):
    """Interfaz mínima: construir payload y ejecutar la llamada HTTP al proveedor."""

    @abstractmethod
    def enviar_pedido(self, proveedor, payload: dict) -> dict:
        """POST al proveedor; debe retornar dict parseado (p. ej. con order_id)."""
        raise NotImplementedError

    @abstractmethod
    def construir_payload_pedido(self, pedido_proveedor, lineas: list[dict]) -> dict:
        """lineas: salida de ServicioPedidos.lineas_para_proveedor()."""
        raise NotImplementedError
