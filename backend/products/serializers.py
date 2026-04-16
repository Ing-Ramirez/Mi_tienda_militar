"""
Franja Pixelada — Serializers de Productos
"""
from rest_framework import serializers
from .models import Category, Product, ProductImage, ProductVariant, ProductReview, ReviewEvidence


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('id', 'name', 'slug', 'description', 'icon', 'image', 'order', 'is_active')


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ('id', 'image', 'alt_text', 'is_primary', 'order')


class ProductVariantSerializer(serializers.ModelSerializer):
    precio_final = serializers.SerializerMethodField()
    imagen = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariant
        fields = (
            'id', 'variant_type', 'name', 'sku',
            'size', 'color', 'color_hex',
            'stock', 'precio_final', 'imagen', 'is_active',
        )

    def get_precio_final(self, obj):
        """Precio absoluto de la variante (ajuste + precio base del producto)."""
        return float(obj.product.price + obj.price_adjustment)

    def get_imagen(self, obj):
        """URL absoluta de la imagen de la variante, o None si no tiene."""
        if not obj.image:
            return None
        request = self.context.get('request')
        return request.build_absolute_uri(obj.image.url) if request else obj.image.url


class ProductListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_slug = serializers.CharField(source='category.slug', read_only=True)
    discount_percentage = serializers.IntegerField(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    average_rating = serializers.FloatField(source='avg_rating', default=None, read_only=True)
    review_count = serializers.IntegerField(source='review_count_val', default=0, read_only=True)
    colores_disponibles = serializers.SerializerMethodField()
    tallas_por_color = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            'id', 'sku', 'name', 'slug', 'short_description',
            'price', 'compare_at_price', 'discount_percentage',
            'benefits',
            'category', 'category_name', 'category_slug',
            'images', 'average_rating', 'review_count',
            'available_sizes', 'stock_by_size', 'requires_size', 'personalization_type',
            'colores_disponibles', 'tallas_por_color',
            'stock', 'status', 'is_featured', 'is_new', 'created_at',
        )

    def _active_stock_variants(self, obj):
        # Usa prefetched variants para evitar N+1 por producto en listados.
        variants = getattr(obj, 'variants', None)
        if variants is None:
            variants = obj.variants.all()
        return sorted(
            [v for v in variants.all() if v.is_active and int(v.stock or 0) > 0],
            key=lambda v: (v.color or '', v.size or ''),
        )

    def get_colores_disponibles(self, obj):
        vistos = {}
        for v in self._active_stock_variants(obj):
            if v.color and v.color not in vistos:
                imagen = None
                if v.image:
                    request = self.context.get('request')
                    imagen = request.build_absolute_uri(v.image.url) if request else v.image.url
                vistos[v.color] = {
                    'color': v.color,
                    'color_hex': v.color_hex or '',
                    'imagen': imagen,
                }
        return list(vistos.values())

    def get_tallas_por_color(self, obj):
        mapa = {}
        for v in self._active_stock_variants(obj):
            clave = v.color or ''
            mapa.setdefault(clave, [])
            if v.size and v.size not in mapa[clave]:
                mapa[clave].append(v.size)
        return mapa


class ProductDetailSerializer(serializers.ModelSerializer):
    variants = ProductVariantSerializer(many=True, read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    discount_percentage = serializers.IntegerField(read_only=True)
    es_bajo_stock = serializers.BooleanField(source='is_low_stock', read_only=True)
    en_stock = serializers.BooleanField(source='is_in_stock', read_only=True)
    average_rating = serializers.FloatField(source='avg_rating', default=None, read_only=True)
    review_count = serializers.IntegerField(source='review_count_val', default=0, read_only=True)

    # Listas derivadas para el selector de color/talla en el frontend
    colores_disponibles = serializers.SerializerMethodField()
    tallas_por_color = serializers.SerializerMethodField()

    class Meta:
        model = Product
        # cost_price, low_stock_threshold y track_inventory son datos internos
        # de operación/contabilidad — nunca se exponen a clientes anónimos.
        fields = (
            'id', 'sku', 'name', 'slug', 'description', 'short_description',
            'price', 'compare_at_price', 'discount_percentage',
            'benefits',
            'category', 'category_name', 'tags',
            'images', 'average_rating', 'review_count',
            'available_sizes', 'stock_by_size', 'requires_size', 'personalization_type',
            'stock', 'status', 'is_featured', 'is_new',
            'en_stock', 'es_bajo_stock',
            'weight', 'meta_title', 'meta_description',
            'variants', 'colores_disponibles', 'tallas_por_color',
            'created_at', 'updated_at',
        )

    def get_colores_disponibles(self, obj):
        """
        Lista de colores únicos con stock, ordenada por el campo `ordering` de la variante.
        Cada entrada incluye color, hex e imagen representativa (primera variante activa de ese color).
        """
        vistos = {}
        variants = sorted(
            [v for v in obj.variants.all() if v.is_active and int(v.stock or 0) > 0],
            key=lambda x: (x.color or '', x.size or ''),
        )
        for v in variants:
            if v.color and v.color not in vistos:
                imagen = None
                if v.image:
                    request = self.context.get('request')
                    imagen = request.build_absolute_uri(v.image.url) if request else v.image.url
                vistos[v.color] = {
                    'color': v.color,
                    'color_hex': v.color_hex or '',
                    'imagen': imagen,
                }
        return list(vistos.values())

    def get_tallas_por_color(self, obj):
        """
        Mapa { color → [tallas con stock] } para filtrado cruzado en el frontend.
        Si no hay colores definidos, retorna { '' → [tallas con stock] }.
        """
        mapa = {}
        variants = sorted(
            [v for v in obj.variants.all() if v.is_active and int(v.stock or 0) > 0],
            key=lambda x: (x.color or '', x.size or ''),
        )
        for v in variants:
            clave = v.color or ''
            mapa.setdefault(clave, [])
            if v.size and v.size not in mapa[clave]:
                mapa[clave].append(v.size)
        return mapa


class ReviewEvidenceSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = ReviewEvidence
        fields = ('id', 'image', 'uploaded_at')

    def get_image(self, obj):
        request = self.context.get('request')
        try:
            return request.build_absolute_uri(obj.image.url) if request else obj.image.url
        except Exception:
            return None


class ReviewReadSerializer(serializers.ModelSerializer):
    """Serializer público para mostrar reseñas aprobadas."""
    user_name = serializers.SerializerMethodField()
    evidence = ReviewEvidenceSerializer(many=True, read_only=True)

    class Meta:
        model = ProductReview
        fields = (
            'id', 'user_name', 'rating', 'title', 'comment',
            'is_verified_purchase', 'evidence', 'created_at',
        )

    def get_user_name(self, obj):
        if obj.user:
            name = obj.user.get_full_name() or obj.user.email
            # Mostrar solo nombre o primera parte del email por privacidad
            if '@' in name:
                parts = name.split('@')
                visible = parts[0]
                if len(visible) > 3:
                    visible = visible[:3] + '***'
                return visible + '@' + parts[1].split('.')[0]
            return name
        return 'Cliente'


class ReviewCreateSerializer(serializers.Serializer):
    """Serializer para crear una reseña con validación de compra verificada."""
    order_id = serializers.UUIDField(
        help_text='ID de la orden que contiene el producto comprado.'
    )
    rating = serializers.IntegerField(min_value=1, max_value=5)
    title = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    comment = serializers.CharField(min_length=10, max_length=2000)

    def validate(self, data):
        request = self.context['request']
        product = self.context['product']

        from orders.models import Order
        try:
            order = Order.objects.get(pk=data['order_id'], user=request.user)
        except Order.DoesNotExist:
            raise serializers.ValidationError(
                {'order_id': 'Orden no encontrada o no pertenece a tu cuenta.'}
            )

        if order.status != 'delivered':
            raise serializers.ValidationError(
                {'order_id': 'Solo puedes calificar productos de pedidos entregados.'}
            )

        # Verificar que el producto esté en esa orden
        has_product = order.items.filter(product=product).exists()
        if not has_product:
            raise serializers.ValidationError(
                {'order_id': 'Este producto no está en la orden indicada.'}
            )

        # Verificar que no exista ya una reseña de este usuario para este producto+orden
        if ProductReview.objects.filter(product=product, user=request.user, order=order).exists():
            raise serializers.ValidationError(
                'Ya has dejado una reseña para este producto en esta orden.'
            )

        data['order'] = order
        return data

    def save(self, product, user):
        # Compra verificada (pedido entregado) → se aprueba automáticamente
        review = ProductReview.objects.create(
            product=product,
            user=user,
            order=self.validated_data['order'],
            rating=self.validated_data['rating'],
            title=self.validated_data.get('title', ''),
            comment=self.validated_data['comment'],
            is_verified_purchase=True,
            status='approved',
        )
        return review


# Alias para compatibilidad con código existente
class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductReview
        fields = ('rating', 'title', 'comment')
