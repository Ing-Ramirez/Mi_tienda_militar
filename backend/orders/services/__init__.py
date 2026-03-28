"""
Franja Pixelada — Servicios de Pedidos

Lógica de negocio para carrito, checkout y cupones.
El envío a proveedores dropshipping solo ocurre tras verificación de pago manual (Neki)
o flujos que invoquen explícitamente despachar_orden_a_proveedores.
"""
from django.conf import settings

from orders.models import Cart, Coupon, Order, OrderItem


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


def create_order_from_cart(cart: Cart, user, data: dict) -> Order:
    """
    Crea un Order a partir del contenido del carrito y limpia el carrito.

    No dispara envío a proveedores (usar tras pago verificado o flujos legacy explícitos).

    Raises:
        ValueError: Si el carrito está vacío.
    """
    if not cart.items.exists():
        raise ValueError('El carrito está vacío.')

    totals = calculate_cart_totals(cart, coupon_code=data.get('coupon_code', ''))

    order = Order.objects.create(
        user=user,
        email=data['email'],
        shipping_full_name=data['shipping_full_name'],
        shipping_phone=data['shipping_phone'],
        shipping_country=data.get('shipping_country', 'Colombia'),
        shipping_department=data['shipping_department'],
        shipping_city=data['shipping_city'],
        shipping_address_line1=data['shipping_address_line1'],
        shipping_address_line2=data.get('shipping_address_line2', ''),
        shipping_postal_code=data.get('shipping_postal_code', ''),
        subtotal=totals['subtotal'],
        shipping_cost=totals['shipping'],
        tax_amount=totals['tax'],
        discount_amount=totals['discount'],
        total=totals['total'],
        customer_notes=data.get('customer_notes', ''),
        coupon_code=data.get('coupon_code', ''),
    )

    for item in cart.items.all():
        price = item.variant.final_price if item.variant else item.product.price
        OrderItem.objects.create(
            order=order,
            product=item.product,
            variant=item.variant,
            product_name=item.product.name,
            product_sku=item.product.sku,
            variant_name=item.variant.name if item.variant else '',
            talla=item.talla,
            bordado=item.bordado,
            rh=item.rh,
            quantity=item.quantity,
            unit_price=price,
            line_total=item.line_total,
        )

    cart.items.all().delete()
    return order


from .neki_checkout import (  # noqa: E402
    build_neki_checkout_preview,
    create_order_neki_from_cart,
    validate_cart_for_checkout,
)

__all__ = [
    'calculate_cart_totals',
    'create_order_from_cart',
    'build_neki_checkout_preview',
    'create_order_neki_from_cart',
    'validate_cart_for_checkout',
]
