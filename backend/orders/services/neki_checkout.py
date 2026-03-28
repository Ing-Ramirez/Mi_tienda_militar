"""
Checkout con pago Neki (comprobante manual): crea orden sin enviar a proveedores.

La verificación del comprobante es en admin; el despacho corre vía Celery al marcar VERIFIED.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.exceptions import ValidationError

from orders.models import Cart, ManualPaymentStatus, Order, OrderItem, PaymentMethod
from products.validators import validate_image_file

if TYPE_CHECKING:
    from users.models import User

logger = logging.getLogger(__name__)


def _stock_para_talla(product, talla: str) -> int:
    if product.requires_size:
        spt = product.stock_by_size
        if isinstance(spt, dict) and spt and talla:
            return int(spt.get(talla, 0))
        return 0
    return product.stock


def validate_cart_for_checkout(cart: Cart) -> None:
    if not cart.items.exists():
        raise ValidationError('El carrito está vacío.')
    for item in cart.items.select_related('product'):
        disponible = _stock_para_talla(item.product, item.talla or '')
        sin_restriccion = disponible == 0 and not item.product.requires_size
        if not sin_restriccion and item.quantity > disponible:
            raise ValidationError(
                f'Stock insuficiente para "{item.product.name}" '
                f'(talla {item.talla or "-"}). '
                f'Disponible: {disponible}, solicitado: {item.quantity}.'
            )


def build_neki_checkout_preview(cart: Cart) -> dict:
    """Datos para pantalla de pago (Neki + totales)."""
    from orders.services import calculate_cart_totals

    empty = not cart.items.exists()
    totals = calculate_cart_totals(cart, coupon_code='') if not empty else {
        'subtotal': 0.0,
        'shipping': 0.0,
        'tax': 0.0,
        'discount': 0.0,
        'total': 0.0,
        'free_shipping_threshold': settings.FREE_SHIPPING_THRESHOLD,
    }
    return {
        'payment_method': PaymentMethod.NEKI,
        'neki': {
            'phone': settings.NEKI_DISPLAY_PHONE,
            'account_holder_name': settings.NEKI_DISPLAY_ACCOUNT_NAME,
        },
        'totals': totals,
        'cart_empty': empty,
    }


def create_order_neki_from_cart(
    *,
    cart: Cart,
    user: User,
    shipping_data: dict,
    payment_proof,
    coupon_code: str = '',
    points_to_use: int = 0,
) -> Order:
    """
    Crea orden con comprobante Neki, estado manual PENDING y limpia el carrito.
    No dispara envío a proveedores.

    Si points_to_use > 0 el servicio de fidelidad valida el saldo, calcula el
    descuento y descuenta los puntos de forma atómica con la creación de la orden.
    """
    from django.db import transaction as db_transaction
    from orders.services import calculate_cart_totals

    validate_cart_for_checkout(cart)

    if not payment_proof:
        raise ValidationError('Debe adjuntar una imagen de comprobante de pago.')
    validate_image_file(payment_proof)

    totals = calculate_cart_totals(cart, coupon_code=coupon_code or '')

    # ── Calcular descuento por puntos ──────────────────────────────────────────
    loyalty_discount = Decimal('0')
    points_applied = 0
    if points_to_use > 0 and user:
        from loyalty.services import preview_redemption
        preview = preview_redemption(
            user=user,
            points_to_use=points_to_use,
            order_total=Decimal(str(totals['total'])),
        )
        if not preview['valid']:
            raise ValidationError(preview['reason'])
        points_applied = preview['points_applied']
        loyalty_discount = Decimal(str(preview['discount_amount']))

    final_total = max(Decimal(str(totals['total'])) - loyalty_discount, Decimal('0'))

    with db_transaction.atomic():
        order = Order(
            user=user,
            email=shipping_data['email'],
            shipping_full_name=shipping_data['shipping_full_name'],
            shipping_phone=shipping_data['shipping_phone'],
            shipping_country=shipping_data.get('shipping_country', 'Colombia'),
            shipping_department=shipping_data['shipping_department'],
            shipping_city=shipping_data['shipping_city'],
            shipping_address_line1=shipping_data['shipping_address_line1'],
            shipping_address_line2=shipping_data.get('shipping_address_line2', ''),
            shipping_postal_code=shipping_data.get('shipping_postal_code', ''),
            subtotal=Decimal(str(totals['subtotal'])),
            shipping_cost=Decimal(str(totals['shipping'])),
            tax_amount=Decimal(str(totals['tax'])),
            discount_amount=Decimal(str(totals['discount'])),
            loyalty_points_used=points_applied,
            loyalty_discount_amount=loyalty_discount,
            total=final_total,
            customer_notes=shipping_data.get('customer_notes', ''),
            coupon_code=coupon_code or '',
            payment_method=PaymentMethod.NEKI,
            manual_payment_status=ManualPaymentStatus.PENDING,
            payment_status='pending',
            status='pending',
        )
        order.payment_proof = payment_proof
        order.save()

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

        # Descontar puntos del saldo (dentro de la misma transacción)
        if points_applied > 0:
            from loyalty.services import redeem_points_for_order
            redeem_points_for_order(user=user, order=order, points_to_use=points_applied)

    logger.info(
        'Orden Neki creada %s usuario=%s total=%s pts_usados=%d',
        order.order_number, user.email, order.total, points_applied,
    )
    return order
