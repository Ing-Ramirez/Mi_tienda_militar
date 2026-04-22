"""
Franja Pixelada — Servicios de Pedidos

Lógica de negocio para carrito, checkout y cupones.
El envío a proveedores dropshipping solo ocurre tras verificación de pago manual (Neki)
o flujos que invoquen explícitamente despachar_orden_a_proveedores.
"""
from django.conf import settings

from orders.models import Cart, Coupon


def calculate_cart_totals(cart: Cart, coupon_code: str = '') -> dict:
    """
    Calcula subtotal, envío, IVA, descuento y total de un carrito.

    Returns:
        Diccionario con claves: subtotal, shipping, tax, discount, total,
        free_shipping_threshold.
    """
    subtotal = float(cart.subtotal)
    shipping = 0.0 if subtotal >= settings.FREE_SHIPPING_THRESHOLD else settings.BASE_SHIPPING_COST
    tax = round(subtotal * settings.TAX_RATE, 2)
    total = subtotal + shipping + tax
    discount = 0.0

    if coupon_code:
        try:
            coupon = Coupon.objects.get(code=coupon_code.upper(), is_active=True)
            if coupon.is_valid and subtotal >= float(coupon.minimum_purchase):
                if coupon.discount_type == 'percentage':
                    discount = round(subtotal * float(coupon.discount_value) / 100, 2)
                else:
                    discount = float(coupon.discount_value)
                total -= discount
        except Coupon.DoesNotExist:
            pass

    return {
        'subtotal': subtotal,
        'shipping': shipping,
        'tax': tax,
        'discount': discount,
        'total': max(total, 0),
        'free_shipping_threshold': settings.FREE_SHIPPING_THRESHOLD,
    }


from .neki_checkout import (  # noqa: E402
    build_neki_checkout_preview,
    create_order_neki_from_cart,
    validate_cart_for_checkout,
)
from .coupons import (  # noqa: E402
    increment_coupon_uses,
    decrement_coupon_uses,
)

__all__ = [
    'calculate_cart_totals',
    'build_neki_checkout_preview',
    'create_order_neki_from_cart',
    'validate_cart_for_checkout',
    'increment_coupon_uses',
    'decrement_coupon_uses',
]
