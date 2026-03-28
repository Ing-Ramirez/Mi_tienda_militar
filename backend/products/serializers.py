"""
Franja Pixelada — Serializers de Productos
"""
from rest_framework import serializers
from .models import Category, Product, ProductImage, ProductVariant, ProductReview


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

    def get_colores_disponibles(self, obj):
        vistos = {}
        for v in obj.variants.filter(is_active=True, stock__gt=0).order_by('color'):
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
        for v in obj.variants.filter(is_active=True, stock__gt=0).order_by('size'):
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
        for v in obj.variants.filter(is_active=True, stock__gt=0).order_by('color'):
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
        for v in obj.variants.filter(is_active=True, stock__gt=0).order_by('size'):
            clave = v.color or ''
            mapa.setdefault(clave, [])
            if v.size and v.size not in mapa[clave]:
                mapa[clave].append(v.size)
        return mapa


class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductReview
        fields = ('rating', 'title', 'comment')
