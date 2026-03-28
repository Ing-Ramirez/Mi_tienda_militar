"""
Sesión HTTP reutilizable para llamadas a APIs de proveedores.

Algunos proveedores (Printful, Dropi y otros) cierran la conexión TLS sin
enviar el alert `close_notify`, lo que Python/urllib3 reporta como:

    SSL: UNEXPECTED_EOF_WHILE_READING

`ssl.OP_IGNORE_UNEXPECTED_EOF` (disponible desde Python 3.11) suprime ese
error sin desactivar ninguna validación de certificados ni bajar el nivel TLS.
"""
from __future__ import annotations

import ssl

import certifi
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context


class _TolerantSSLAdapter(HTTPAdapter):
    """
    HTTPAdapter que:
    - Carga el bundle de CAs de certifi (necesario en python:slim, que no incluye
      el CA store del SO).
    - Ignora EOF inesperado al cierre TLS (OP_IGNORE_UNEXPECTED_EOF), que es lo
      que generan Printful y otros proveedores al cerrar la conexión sin close_notify.
    """

    def init_poolmanager(self, num_pools, maxsize, block=False, **kw):
        ctx = create_urllib3_context()
        ctx.options |= ssl.OP_IGNORE_UNEXPECTED_EOF
        # Cargar el bundle de certifi explícitamente; sin esto, python:slim no
        # puede verificar certificados firmados por Let's Encrypt ni DigiCert.
        ctx.load_verify_locations(cafile=certifi.where())
        kw["ssl_context"] = ctx
        super().init_poolmanager(num_pools, maxsize, block=block, **kw)


def proveedor_session() -> requests.Session:
    """
    Devuelve una requests.Session configurada para llamadas a APIs de proveedores.

    Uso:
        session = proveedor_session()
        resp = session.get(url, headers=headers, timeout=20)
    """
    session = requests.Session()
    session.mount("https://", _TolerantSSLAdapter())
    return session
