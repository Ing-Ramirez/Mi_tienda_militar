"""
Franja Pixelada — Serializers de Pedidos
"""
from rest_framework import serializers
from .models import Cart, CartItem, Order, OrderItem
from .media_tokens import signed_payment_proof_absolute_url


class CartItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_price = serializers.DecimalField(source='product.price', max_digits=12,
                                              decimal_places=2, read_only=True)
    line_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = ('id', 'product', 'product_name', 'product_price', 'variant',
                  'talla', 'bordado', 'rh', 'quantity', 'price_at_addition', 'line_total')


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_items = serializers.IntegerField(read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Cart
        fields = ('id', 'items', 'total_items', 'subtotal', 'updated_at')


class OrderItemReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = (
            'id', 'product_name', 'product_sku', 'variant_name',
            'talla', 'bordado', 'rh', 'quantity', 'unit_price', 'line_total',
        )


class OrderSummarySerializer(serializers.ModelSerializer):
    """Listado de pedidos (sin ítems anidados)."""
    items_count = serializers.IntegerField(read_only=True)
    coupon_discount = serializers.DecimalField(
        source='discount_amount', max_digits=12, decimal_places=2, read_only=True,
    )

    class Meta:
        model = Order
        fields = (
            'id', 'order_number', 'status', 'payment_status', 'payment_method',
            'subtotal', 'shipping_cost', 'tax_amount',
            'total', 'coupon_code', 'coupon_discount',
            'loyalty_discount_amount', 'loyalty_points_used',
            'manual_payment_status', 'created_at', 'items_count',
        )


class OrderDetailSerializer(serializers.ModelSerializer):
    items = OrderItemReadSerializer(many=True, read_only=True)
    coupon_discount = serializers.DecimalField(
        source='discount_amount', max_digits=12, decimal_places=2, read_only=True,
    )
    payment_proof_url = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            'id', 'order_number', 'status', 'payment_status', 'payment_method',
            'subtotal', 'shipping_cost', 'tax_amount', 'discount_amount',
            'total', 'coupon_code', 'coupon_discount',
            'loyalty_discount_amount', 'loyalty_points_used',
            'shipping_full_name', 'shipping_phone',
            'shipping_address_line1', 'shipping_city', 'shipping_department',
            'shipping_country', 'shipping_address_line2', 'shipping_postal_code',
            'email', 'customer_notes',
            'manual_payment_status', 'created_at', 'updated_at',
            'items', 'payment_proof_url',
        )

    def get_payment_proof_url(self, obj):
        return signed_payment_proof_absolute_url(self.context.get('request'), obj)
