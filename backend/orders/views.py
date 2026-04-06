import mimetypes

from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction as db_transaction
from django.db.models import Count
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Cart, CartItem, Coupon, Order, OrderItem
from .serializers import (
    CartSerializer,
    CartItemSerializer,
    OrderSummarySerializer,
    OrderDetailSerializer,
)
from .media_tokens import parse_payment_proof_token
from .throttles import PaymentProofMediaAnonThrottle


# ── Helpers de validación de stock ────────────────────────────────────────────

def _stock_para_talla(product, talla: str) -> int:
    """
    Retorna el stock controlable para un producto+talla.
    - CON TALLA (requires_size=True):  lee stock_by_size[talla]; 0 si la talla no existe.
    - SIN TALLA  (requires_size=False): devuelve product.stock global (ignora el parámetro talla).
    Retornar 0 significa "sin datos de stock" → la validación lo trata como sin restricción.
    """
    if product.requires_size:
        spt = product.stock_by_size
        if isinstance(spt, dict) and spt and talla:
            return int(spt.get(talla, 0))
        return 0  # sin datos para esa talla → no permitir
    return product.stock  # sin talla: stock global


def _qty_en_carrito(cart, product, talla: str, exclude_item_id=None) -> int:
    """Suma de cantidades ya en carrito para el par producto+talla."""
    qs = cart.items.filter(product=product, talla=talla)
    if exclude_item_id:
        qs = qs.exclude(id=exclude_item_id)
    return sum(item.quantity for item in qs)


def _validar_stock(product, talla: str, qty_solicitada: int,
                   cart=None, exclude_item_id=None):
    """
    Verifica que qty_solicitada no supere el stock disponible.
    Diferencia entre productos con y sin talla:
    - CON TALLA  (requires_size=True):  disponible=0 → bloquear (talla sin stock).
    - SIN TALLA  (requires_size=False): disponible=0 → sin restricción (permitir).
    Retorna (ok: bool, disponible: int, en_carrito: int).
    """
    disponible = _stock_para_talla(product, talla)
    if disponible == 0:
        if product.requires_size:
            # Talla sin stock registrado → rechazar
            return False, 0, 0
        # Sin talla y sin stock definido → sin restricción
        return True, 0, 0
    en_carrito = _qty_en_carrito(cart, product, talla, exclude_item_id) if cart else 0
    ok = (en_carrito + qty_solicitada) <= disponible
    return ok, disponible, en_carrito


class CartViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = CartSerializer

    def _get_cart(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return cart

    @action(detail=False, methods=['get'])
    def my_cart(self, request):
        cart = self._get_cart(request)
        return Response(CartSerializer(cart).data)

    @action(detail=False, methods=['post'])
    def add_item(self, request):
        cart = self._get_cart(request)
        # Acepta 'product_id' (convención API) y 'product' (alias legacy del frontend SPA)
        product_id = request.data.get('product_id') or request.data.get('product')
        talla = request.data.get('talla', '')
        bordado = request.data.get('bordado', '').upper()[:30]
        rh = request.data.get('rh', '')
        try:
            quantity = int(request.data.get('quantity', 1))
        except (TypeError, ValueError):
            return Response(
                {'detail': 'Cantidad no válida.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if quantity < 1:
            return Response(
                {'detail': 'La cantidad debe ser al menos 1.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from products.models import Product, ProductVariant
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response({'detail': 'Producto no encontrado.'}, status=404)

        variant = None
        if request.data.get('variant'):
            try:
                variant = ProductVariant.objects.get(id=request.data['variant'])
            except ProductVariant.DoesNotExist:
                pass
            if variant and variant.product_id != product.id:
                return Response(
                    {'detail': 'Variante inválida para el producto seleccionado.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        has_personalization = bool(bordado or rh)

        # ── Validar stock y crear ítem de forma atómica (evita overselling) ────
        with db_transaction.atomic():
            product = Product.objects.select_for_update().get(id=product_id)
            price = variant.final_price if variant else product.price

            ok, disponible, en_carrito = _validar_stock(
                product, talla, quantity, cart=cart
            )
            if not ok:
                restante = max(0, disponible - en_carrito)
                talla_label = talla or 'seleccionada'
                return Response({
                    'detail': (
                        f'Stock insuficiente para la talla {talla_label}. '
                        f'Disponible: {disponible}, ya en carrito: {en_carrito}, '
                        f'puedes agregar: {restante}.'
                    ),
                    'stock_disponible': disponible,
                    'ya_en_carrito': en_carrito,
                    'qty_disponible': restante,
                }, status=status.HTTP_400_BAD_REQUEST)

            if has_personalization:
                CartItem.objects.create(
                    cart=cart, product=product, variant=variant,
                    talla=talla, bordado=bordado, rh=rh,
                    quantity=quantity, price_at_addition=price
                )
            else:
                item, created = CartItem.objects.get_or_create(
                    cart=cart, product=product, variant=variant,
                    talla=talla, bordado='', rh='',
                    defaults={'quantity': quantity, 'price_at_addition': price}
                )
                if not created:
                    item.quantity += quantity
                    item.save()

        return Response(CartSerializer(cart).data, status=201)

    @action(detail=False, methods=['patch'], url_path='update_item/(?P<item_id>[^/.]+)')
    def update_item(self, request, item_id=None):
        cart = self._get_cart(request)
        try:
            item = CartItem.objects.get(id=item_id, cart=cart)
        except CartItem.DoesNotExist:
            return Response({'detail': 'Ítem no encontrado.'}, status=404)
        try:
            quantity = int(request.data.get('quantity', item.quantity))
        except (TypeError, ValueError):
            return Response(
                {'detail': 'Cantidad no válida.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if quantity <= 0:
            item.delete()
        else:
            # Validar stock de forma atómica (evita overselling concurrente)
            with db_transaction.atomic():
                product = item.product.__class__.objects.select_for_update().get(
                    id=item.product_id
                )
                ok, disponible, _ = _validar_stock(
                    product, item.talla, quantity,
                    cart=cart, exclude_item_id=item.id
                )
                if not ok:
                    talla_label = item.talla or 'seleccionada'
                    return Response({
                        'detail': (
                            f'Stock insuficiente para la talla {talla_label}. '
                            f'Máximo disponible: {disponible} unidades.'
                        ),
                        'stock_disponible': disponible,
                    }, status=status.HTTP_400_BAD_REQUEST)
                item.quantity = quantity
                item.save()
        return Response(CartSerializer(cart).data)

    @action(detail=False, methods=['delete'], url_path='remove_item/(?P<item_id>[^/.]+)')
    def remove_item(self, request, item_id=None):
        cart = self._get_cart(request)
        CartItem.objects.filter(id=item_id, cart=cart).delete()
        return Response(CartSerializer(cart).data)

    @action(detail=False, methods=['delete'])
    def clear(self, request):
        cart = self._get_cart(request)
        cart.items.all().delete()
        return Response({'detail': 'Carrito vaciado.'})

    @action(detail=False, methods=['get'])
    def calculate_totals(self, request):
        cart = self._get_cart(request)
        subtotal = float(cart.subtotal)
        shipping = 0.0 if subtotal >= settings.FREE_SHIPPING_THRESHOLD else settings.BASE_SHIPPING_COST
        tax = round(subtotal * settings.TAX_RATE, 2)
        total = subtotal + shipping + tax
        coupon_code = request.query_params.get('coupon', '')
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
        return Response({
            'subtotal': subtotal,
            'shipping': shipping,
            'tax': tax,
            'discount': discount,
            'total': max(total, 0),
            'free_shipping_threshold': settings.FREE_SHIPPING_THRESHOLD,
        })


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Order.objects.filter(user=self.request.user)
            .prefetch_related('items')
            .annotate(items_count=Count('items', distinct=True))
        )

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return OrderDetailSerializer
        return OrderSummarySerializer

    @action(detail=False, methods=['post'])
    def checkout(self, request):
        from products.models import Product, ProductVariant

        cart, _ = Cart.objects.get_or_create(user=request.user)
        if not cart.items.exists():
            return Response({'detail': 'El carrito está vacío.'}, status=400)

        required = ['shipping_full_name', 'shipping_phone', 'shipping_department',
                    'shipping_city', 'shipping_address_line1', 'email']
        for field in required:
            if not request.data.get(field):
                return Response({'detail': f'El campo {field} es requerido.'}, status=400)

        with db_transaction.atomic():
            # Bloquear fila de carrito + ítems para snapshot consistente
            cart = Cart.objects.select_for_update().get(pk=cart.pk)
            cart_items = list(
                cart.items.select_for_update()
            )

            # Lock de productos y variantes para validación concurrente consistente
            product_ids = {item.product_id for item in cart_items if item.product_id}
            variant_ids = {item.variant_id for item in cart_items if item.variant_id}
            locked_products = {
                p.id: p for p in Product.objects.select_for_update().filter(id__in=product_ids)
            }
            locked_variants = {
                v.id: v for v in ProductVariant.objects.select_for_update().filter(id__in=variant_ids)
            }

            for item in cart_items:
                product = locked_products.get(item.product_id)
                if not product:
                    return Response(
                        {'detail': 'Uno de los productos del carrito ya no está disponible.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                variant = locked_variants.get(item.variant_id) if item.variant_id else None
                if variant and variant.product_id != product.id:
                    return Response(
                        {
                            'detail': (
                                f'La variante asociada a "{product.name}" no es válida para ese producto.'
                            )
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                disponible = _stock_para_talla(product, item.talla or '')
                # Para productos SIN talla: disponible=0 = sin restricción → skip
                # Para productos CON talla: disponible=0 = talla agotada → bloquear
                sin_restriccion = (disponible == 0 and not product.requires_size)
                if not sin_restriccion and item.quantity > disponible:
                    talla_label = item.talla or '-'
                    return Response({
                        'detail': (
                            f'Stock insuficiente para "{product.name}" '
                            f'(talla {talla_label}). '
                            f'Disponible: {disponible}, solicitado: {item.quantity}.'
                        ),
                        'producto': product.name,
                        'talla': talla_label,
                        'stock_disponible': disponible,
                        'qty_solicitada': item.quantity,
                    }, status=status.HTTP_400_BAD_REQUEST)

            subtotal = float(cart.subtotal)
            shipping = 0.0 if subtotal >= settings.FREE_SHIPPING_THRESHOLD else settings.BASE_SHIPPING_COST
            tax = round(subtotal * settings.TAX_RATE, 2)
            total = subtotal + shipping + tax

            order = Order.objects.create(
                user=request.user,
                email=request.data['email'],
                shipping_full_name=request.data['shipping_full_name'],
                shipping_phone=request.data['shipping_phone'],
                shipping_country=request.data.get('shipping_country', 'Colombia'),
                shipping_department=request.data['shipping_department'],
                shipping_city=request.data['shipping_city'],
                shipping_address_line1=request.data['shipping_address_line1'],
                shipping_address_line2=request.data.get('shipping_address_line2', ''),
                shipping_postal_code=request.data.get('shipping_postal_code', ''),
                subtotal=subtotal,
                shipping_cost=shipping,
                tax_amount=tax,
                total=total,
                customer_notes=request.data.get('customer_notes', ''),
                coupon_code=request.data.get('coupon_code', ''),
            )

            for item in cart_items:
                product = locked_products[item.product_id]
                variant = locked_variants.get(item.variant_id) if item.variant_id else None
                price = variant.final_price if variant else product.price
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    variant=variant,
                    product_name=product.name,
                    product_sku=product.sku,
                    variant_name=variant.name if variant else '',
                    talla=item.talla,
                    bordado=item.bordado,
                    rh=item.rh,
                    quantity=item.quantity,
                    unit_price=price,
                    line_total=item.line_total,
                )

            cart.items.all().delete()

        return Response({
            'order_number': order.order_number,
            'total': order.total,
            'status': order.status,
        }, status=201)


class CheckoutNekiView(APIView):
    """
    Flujo Neki (pago manual con comprobante).

    GET  /api/v1/orders/checkout/  → datos de pago ficticios + totales del carrito
    POST /api/v1/orders/checkout/  → multipart: envío + payment_proof (imagen obligatoria)
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        from orders.services import build_neki_checkout_preview

        cart, _ = Cart.objects.get_or_create(user=request.user)
        return Response(build_neki_checkout_preview(cart))

    def post(self, request):
        from orders.services import create_order_neki_from_cart

        cart, _ = Cart.objects.get_or_create(user=request.user)
        if not cart.items.exists():
            return Response({'detail': 'El carrito está vacío.'}, status=status.HTTP_400_BAD_REQUEST)

        required = [
            'shipping_full_name', 'shipping_phone', 'shipping_department',
            'shipping_city', 'shipping_address_line1', 'email',
        ]
        for field in required:
            if not request.data.get(field):
                return Response(
                    {'detail': f'El campo {field} es requerido.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        proof = request.FILES.get('payment_proof')
        if not proof:
            return Response(
                {'detail': 'Debe adjuntar el comprobante de pago (imagen).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        shipping_data = {
            'email': request.data['email'],
            'shipping_full_name': request.data['shipping_full_name'],
            'shipping_phone': request.data['shipping_phone'],
            'shipping_country': request.data.get('shipping_country', 'Colombia'),
            'shipping_department': request.data['shipping_department'],
            'shipping_city': request.data['shipping_city'],
            'shipping_address_line1': request.data['shipping_address_line1'],
            'shipping_address_line2': request.data.get('shipping_address_line2', ''),
            'shipping_postal_code': request.data.get('shipping_postal_code', ''),
            'customer_notes': request.data.get('customer_notes', ''),
        }
        coupon_code = request.data.get('coupon_code', '')
        points_to_use = int(request.data.get('points_to_use', 0) or 0)

        try:
            order = create_order_neki_from_cart(
                cart=cart,
                user=request.user,
                shipping_data=shipping_data,
                payment_proof=proof,
                coupon_code=coupon_code,
                points_to_use=points_to_use,
            )
        except ValidationError as e:
            msgs = list(e.messages) if hasattr(e, 'messages') else [str(e)]
            return Response({'detail': msgs}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                'id': str(order.id),
                'order_number': order.order_number,
                'total_amount': str(order.total_amount),
                'status': order.status,
                'manual_payment_status': order.manual_payment_status,
                'payment_method': order.payment_method,
            },
            status=status.HTTP_201_CREATED,
        )


class OrderPaymentProofMediaView(APIView):
    """
    Comprobante Neki para el dueño del pedido (URL firmada en payment_proof_url).
    """
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [PaymentProofMediaAnonThrottle]

    def get(self, request, pk):
        token = request.query_params.get('t')
        if not token:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        try:
            data = parse_payment_proof_token(token)
        except signing.SignatureExpired:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        except signing.BadSignature:
            return Response(status=status.HTTP_403_FORBIDDEN)
        if str(data['o']) != str(pk):
            return Response(status=status.HTTP_403_FORBIDDEN)
        order = get_object_or_404(Order, pk=pk)
        if not order.payment_proof or order.payment_proof.name != data['f']:
            return Response(status=status.HTTP_403_FORBIDDEN)
        if str(order.user_id) != str(data['u']):
            return Response(status=status.HTTP_403_FORBIDDEN)
        try:
            fp = order.payment_proof.open('rb')
        except FileNotFoundError:
            return Response(status=status.HTTP_404_NOT_FOUND)
        mime, _ = mimetypes.guess_type(order.payment_proof.name)
        resp = FileResponse(fp, content_type=mime or 'application/octet-stream')
        resp['Cache-Control'] = 'private, no-store'
        return resp


class CouponValidateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        code = request.data.get('code', '').upper()
        subtotal = float(request.data.get('subtotal', 0))
        try:
            coupon = Coupon.objects.get(code=code, is_active=True)
        except Coupon.DoesNotExist:
            return Response({'valid': False, 'detail': 'Cupón no encontrado.'}, status=404)
        if not coupon.is_valid:
            return Response({'valid': False, 'detail': 'Cupón expirado o agotado.'})
        if subtotal < float(coupon.minimum_purchase):
            return Response({
                'valid': False,
                'detail': f'Compra mínima requerida: COP {coupon.minimum_purchase:,.0f}'
            })
        discount = (
            round(subtotal * float(coupon.discount_value) / 100, 2)
            if coupon.discount_type == 'percentage'
            else float(coupon.discount_value)
        )
        return Response({
            'valid': True,
            'discount_type': coupon.discount_type,
            'discount_value': float(coupon.discount_value),
            'discount_amount': discount,
        })
