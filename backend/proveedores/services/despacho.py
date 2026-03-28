"""
Despacho post-checkout: agrupa ítems por proveedor y encola envío asíncrono.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from orders.models import Order

logger = logging.getLogger(__name__)


def despachar_orden_a_proveedores(order: Order) -> list[UUID]:
    """
    Tras crear la orden local, genera un SupplierOrder por cada proveedor con
    ítems vinculados (is_active, tipo api_rest, endpoint y status activo/prueba)
    y encola enviar_pedido_a_proveedor.

    Returns:
        IDs de SupplierOrder creados en esta ejecución.
    """
    from proveedores.models import SupplierOrder, Supplier, IntegrationType
    from proveedores.services.pedidos import ServicioPedidos
    from proveedores.services.vinculos import resolver_vinculo_para_order_item
    from proveedores.tasks import enviar_pedido_a_proveedor

    groups: dict[UUID, list] = defaultdict(list)

    for item in order.items.select_related('product', 'variant').all():
        if not item.product_id:
            continue
        vinculo = resolver_vinculo_para_order_item(item)
        if not vinculo:
            continue
        proveedor = vinculo.supplier_variant.supplier_product.supplier
        if proveedor.status not in ('activo', 'prueba'):
            continue
        if proveedor.integration_type not in (
            IntegrationType.API_REST,
            IntegrationType.MOCK,
        ):
            continue
        if proveedor.integration_type != IntegrationType.MOCK and not (
            proveedor.endpoint_base or ''
        ).strip():
            logger.warning(
                'Omitiendo proveedor %s: sin endpoint_base configurado',
                proveedor.slug,
            )
            continue
        groups[proveedor.id].append(item)

    creados: list[UUID] = []
    svc = ServicioPedidos()

    for proveedor_id, items in groups.items():
        proveedor = Supplier.objects.get(pk=proveedor_id)
        if SupplierOrder.objects.filter(local_order=order, supplier=proveedor).exists():
            continue

        total = sum((it.line_total for it in items), Decimal('0'))
        pedido_prov = svc.crear_pedido_proveedor(order, proveedor, total=total)
        creados.append(pedido_prov.id)
        enviar_pedido_a_proveedor.delay(str(pedido_prov.id))
        logger.info(
            'SupplierOrder %s encolado → proveedor=%s líneas=%s',
            pedido_prov.id,
            proveedor.slug,
            len(items),
        )

    return creados
