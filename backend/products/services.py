"""
Franja Pixelada — Servicios de Productos

Lógica de negocio para inventario y stock.
"""
from django.db import transaction
from .models import Product, ProductVariant, InventoryLog


def adjust_stock(product: Product, quantity_change: int, action: str,
                 notes: str = '', created_by=None, variant: ProductVariant = None) -> Product:
    """
    Ajusta el stock de un producto y registra el movimiento en InventoryLog.

    Args:
        product: Instancia del producto a ajustar.
        quantity_change: Positivo para entradas, negativo para salidas.
        action: Uno de 'add', 'remove', 'sale', 'return', 'adjustment'.
        notes: Texto descriptivo del motivo del ajuste.
        created_by: Usuario que realizó el cambio (puede ser None).
        variant: Variante específica si aplica.

    Returns:
        Producto actualizado.

    Raises:
        ValueError: Si el stock resultante sería negativo.
    """
    with transaction.atomic():
        product = Product.objects.select_for_update().get(pk=product.pk)
        stock_before = product.stock
        stock_after = stock_before + quantity_change

        if stock_after < 0:
            raise ValueError(
                f'Stock insuficiente. Disponible: {stock_before}, solicitado: {abs(quantity_change)}'
            )

        product.stock = stock_after
        if stock_after == 0:
            product.status = 'out_of_stock'
        elif stock_before == 0 and stock_after > 0 and product.status == 'out_of_stock':
            product.status = 'active'
        product.save(update_fields=['stock', 'status'])

        InventoryLog.objects.create(
            product=product,
            variant=variant,
            action=action,
            quantity_change=quantity_change,
            stock_before=stock_before,
            stock_after=stock_after,
            notes=notes,
            created_by=created_by,
        )

    return product
