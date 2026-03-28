from .base import BaseProveedorAdapter
from .dropi import DropiAdapter
from .mock import MockProveedorAdapter
from .registry import get_adapter
from .rest_generico import RestGenericoAdapter

__all__ = [
    'BaseProveedorAdapter',
    'DropiAdapter',
    'MockProveedorAdapter',
    'RestGenericoAdapter',
    'get_adapter',
]
