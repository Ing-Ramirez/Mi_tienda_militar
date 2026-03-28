"""
Registro de adaptadores por valor de Supplier.adapter.
"""
from __future__ import annotations

from ...models import ProviderAdapter
from .base import BaseProveedorAdapter
from .dropi import DropiAdapter
from .mock import MockProveedorAdapter
from .rest_generico import RestGenericoAdapter

_REGISTRY: dict[str, type[BaseProveedorAdapter]] = {
    ProviderAdapter.REST_GENERICO: RestGenericoAdapter,
    ProviderAdapter.DROPI: DropiAdapter,
    ProviderAdapter.MOCK: MockProveedorAdapter,
}


def get_adapter(proveedor) -> BaseProveedorAdapter:
    cls = _REGISTRY.get(proveedor.adapter)
    if cls is None:
        return RestGenericoAdapter()
    return cls()
