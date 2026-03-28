"""
Resolución de LinkedProduct para ítems de pedido (checkout / envío a proveedor).
"""
from __future__ import annotations

from ..models import LinkedProduct


def resolver_vinculo_para_order_item(item) -> LinkedProduct | None:
    """
    Elige el vínculo activo entre el producto local del ítem y una SupplierVariant.

    Prioridad:
      1) Coincidencia SKU variante local == SKU en SupplierVariant.
      2) Coincidencia de talla en atributos del proveedor (talla / size) con item.talla.
      3) Primer vínculo activo si no hay criterio más específico.
    """
    if not item.product_id:
        return None

    qs = LinkedProduct.objects.filter(
        local_product_id=item.product_id,
        is_active=True,
    ).select_related('supplier_variant__supplier_product__supplier')

    if not qs.exists():
        return None

    if item.variant_id and item.variant:
        sku_local = (item.variant.sku or '').strip()
        if sku_local:
            match = qs.filter(supplier_variant__sku=sku_local).first()
            if match:
                return match

    talla = (item.talla or '').strip()
    if talla:
        talla_u = talla.upper()
        for v in qs:
            attr = v.supplier_variant.attributes or {}
            vt = str(attr.get('talla') or attr.get('size') or '').strip().upper()
            if vt and vt == talla_u:
                return v

    return qs.first()
