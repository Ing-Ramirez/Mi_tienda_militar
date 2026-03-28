from rest_framework import serializers

from .models import Supplier, SupplierLog, SupplierVariant, LinkedProduct


class ProveedorEstadoSerializer(serializers.ModelSerializer):
    """Vista resumida del proveedor para el panel de monitoreo interno."""
    total_productos          = serializers.SerializerMethodField()
    total_pedidos_pendientes = serializers.SerializerMethodField()
    ultimo_log               = serializers.SerializerMethodField()

    class Meta:
        model  = Supplier
        fields = [
            'id', 'name', 'slug', 'status', 'integration_type',
            'origin_currency', 'stock_buffer',
            'total_productos', 'total_pedidos_pendientes', 'ultimo_log',
            'updated_at',
        ]

    def get_total_productos(self, obj) -> int:
        return obj.productos.count()

    def get_total_pedidos_pendientes(self, obj) -> int:
        return obj.pedidos.filter(status='pendiente_envio').count()

    def get_ultimo_log(self, obj) -> dict | None:
        log = obj.logs.first()
        if not log:
            return None
        return {
            'tipo':      log.event_type,
            'estado':    log.status,
            'mensaje':   log.message,
            'timestamp': log.timestamp,
        }


class LogProveedorSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SupplierLog
        fields = ['id', 'event_type', 'status', 'message', 'timestamp']


class VarianteProveedorCatalogoSerializer(serializers.ModelSerializer):
    """Vista del catálogo del proveedor — para el panel de selección de productos."""
    proveedor_nombre = serializers.CharField(source='supplier_product.supplier.name', read_only=True)
    producto_nombre  = serializers.CharField(source='supplier_product.name', read_only=True)
    ya_vinculado     = serializers.SerializerMethodField()

    class Meta:
        model  = SupplierVariant
        fields = [
            'id', 'proveedor_nombre', 'producto_nombre',
            'sku', 'attributes', 'base_price', 'calculated_price',
            'stock', 'status', 'image_url', 'ya_vinculado',
            'updated_at',
        ]

    def get_ya_vinculado(self, obj) -> bool:
        return obj.vinculos.filter(is_active=True).exists()


class ProductoVinculadoSerializer(serializers.ModelSerializer):
    """
    Serializer completo para crear, editar y listar vínculos.
    Incluye los campos calculados de stock para visualización en el panel.
    """
    # Datos del proveedor (solo lectura)
    sku_proveedor    = serializers.CharField(source='supplier_variant.sku', read_only=True)
    stock_proveedor  = serializers.IntegerField(read_only=True)
    stock_visible    = serializers.IntegerField(read_only=True)
    nombre_producto  = serializers.CharField(source='local_product.name', read_only=True)
    proveedor_nombre = serializers.CharField(
        source='supplier_variant.supplier_product.supplier.name', read_only=True,
    )

    class Meta:
        model  = LinkedProduct
        fields = [
            'id',
            # Relaciones (escribibles al crear)
            'supplier_variant', 'local_product',
            # Info de contexto (solo lectura)
            'sku_proveedor', 'proveedor_nombre', 'nombre_producto',
            # Reglas
            'max_stock', 'price_margin',
            'is_active', 'sync_enabled',
            # Calculados (solo lectura)
            'stock_proveedor', 'stock_visible', 'calculated_stock', 'last_recalculated_at',
            'created_at',
        ]
        read_only_fields = [
            'id', 'calculated_stock', 'last_recalculated_at', 'created_at',
        ]
