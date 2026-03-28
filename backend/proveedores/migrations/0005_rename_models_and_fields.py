"""
Migration: Rename proveedores models and fields to English naming convention.

Models renamed:
  Proveedor          → Supplier      (db_table: proveedores_proveedor → proveedores_supplier)
  ProductoProveedor  → SupplierProduct
  VarianteProveedor  → SupplierVariant
  ProductoVinculado  → LinkedProduct
  PedidoProveedor    → SupplierOrder
  TrackingProveedor  → SupplierTracking
  LogProveedor       → SupplierLog

Fields renamed per model (verbose_names in Spanish, kept in models.py).
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('proveedores', '0004_proveedor_mock_tipo_adapter'),
    ]

    operations = [
        # ── Rename Models (and their DB tables) ──────────────────────────────

        migrations.RenameModel(
            old_name='Proveedor',
            new_name='Supplier',
        ),
        migrations.RenameModel(
            old_name='ProductoProveedor',
            new_name='SupplierProduct',
        ),
        migrations.RenameModel(
            old_name='VarianteProveedor',
            new_name='SupplierVariant',
        ),
        migrations.RenameModel(
            old_name='ProductoVinculado',
            new_name='LinkedProduct',
        ),
        migrations.RenameModel(
            old_name='PedidoProveedor',
            new_name='SupplierOrder',
        ),
        migrations.RenameModel(
            old_name='TrackingProveedor',
            new_name='SupplierTracking',
        ),
        migrations.RenameModel(
            old_name='LogProveedor',
            new_name='SupplierLog',
        ),

        # ── Rename Fields: Supplier (ex-Proveedor) ────────────────────────────

        migrations.RenameField(
            model_name='Supplier',
            old_name='nombre',
            new_name='name',
        ),
        migrations.RenameField(
            model_name='Supplier',
            old_name='tipo_integracion',
            new_name='integration_type',
        ),
        migrations.RenameField(
            model_name='Supplier',
            old_name='estado',
            new_name='status',
        ),
        migrations.RenameField(
            model_name='Supplier',
            old_name='politica_precios',
            new_name='pricing_policy',
        ),
        migrations.RenameField(
            model_name='Supplier',
            old_name='moneda_origen',
            new_name='origin_currency',
        ),
        migrations.RenameField(
            model_name='Supplier',
            old_name='buffer_stock',
            new_name='stock_buffer',
        ),
        migrations.RenameField(
            model_name='Supplier',
            old_name='tiempo_entrega_dias',
            new_name='delivery_days',
        ),
        migrations.RenameField(
            model_name='Supplier',
            old_name='notas',
            new_name='notes',
        ),
        migrations.RenameField(
            model_name='Supplier',
            old_name='creado_en',
            new_name='created_at',
        ),
        migrations.RenameField(
            model_name='Supplier',
            old_name='actualizado_en',
            new_name='updated_at',
        ),
        # _credenciales uses db_column='credenciales', so we just rename the Python attribute
        migrations.RenameField(
            model_name='Supplier',
            old_name='_credenciales',
            new_name='_credentials',
        ),

        # ── Rename Fields: SupplierProduct (ex-ProductoProveedor) ─────────────

        migrations.RenameField(
            model_name='SupplierProduct',
            old_name='proveedor',
            new_name='supplier',
        ),
        migrations.RenameField(
            model_name='SupplierProduct',
            old_name='proveedor_product_id',
            new_name='supplier_product_id',
        ),
        migrations.RenameField(
            model_name='SupplierProduct',
            old_name='nombre',
            new_name='name',
        ),
        migrations.RenameField(
            model_name='SupplierProduct',
            old_name='descripcion',
            new_name='description',
        ),
        migrations.RenameField(
            model_name='SupplierProduct',
            old_name='categoria',
            new_name='category_name',
        ),
        migrations.RenameField(
            model_name='SupplierProduct',
            old_name='estado',
            new_name='status',
        ),
        migrations.RenameField(
            model_name='SupplierProduct',
            old_name='datos_raw',
            new_name='raw_data',
        ),
        migrations.RenameField(
            model_name='SupplierProduct',
            old_name='fecha_sync',
            new_name='synced_at',
        ),
        migrations.RenameField(
            model_name='SupplierProduct',
            old_name='producto_local',
            new_name='local_product',
        ),
        migrations.RenameField(
            model_name='SupplierProduct',
            old_name='creado_en',
            new_name='created_at',
        ),

        # ── Rename Fields: SupplierVariant (ex-VarianteProveedor) ─────────────

        migrations.RenameField(
            model_name='SupplierVariant',
            old_name='producto',
            new_name='supplier_product',
        ),
        migrations.RenameField(
            model_name='SupplierVariant',
            old_name='proveedor_variant_id',
            new_name='supplier_variant_id',
        ),
        migrations.RenameField(
            model_name='SupplierVariant',
            old_name='precio_base',
            new_name='base_price',
        ),
        migrations.RenameField(
            model_name='SupplierVariant',
            old_name='precio_calculado',
            new_name='calculated_price',
        ),
        migrations.RenameField(
            model_name='SupplierVariant',
            old_name='atributos',
            new_name='attributes',
        ),
        migrations.RenameField(
            model_name='SupplierVariant',
            old_name='estado',
            new_name='status',
        ),
        migrations.RenameField(
            model_name='SupplierVariant',
            old_name='imagen_url',
            new_name='image_url',
        ),
        migrations.RenameField(
            model_name='SupplierVariant',
            old_name='ultima_actualizacion',
            new_name='updated_at',
        ),

        # ── Rename Fields: LinkedProduct (ex-ProductoVinculado) ───────────────

        migrations.RenameField(
            model_name='LinkedProduct',
            old_name='variante_proveedor',
            new_name='supplier_variant',
        ),
        migrations.RenameField(
            model_name='LinkedProduct',
            old_name='producto_local',
            new_name='local_product',
        ),
        migrations.RenameField(
            model_name='LinkedProduct',
            old_name='stock_maximo',
            new_name='max_stock',
        ),
        migrations.RenameField(
            model_name='LinkedProduct',
            old_name='margen_precio_override',
            new_name='price_margin',
        ),
        migrations.RenameField(
            model_name='LinkedProduct',
            old_name='activo',
            new_name='is_active',
        ),
        migrations.RenameField(
            model_name='LinkedProduct',
            old_name='sincronizar',
            new_name='sync_enabled',
        ),
        migrations.RenameField(
            model_name='LinkedProduct',
            old_name='stock_calculado',
            new_name='calculated_stock',
        ),
        migrations.RenameField(
            model_name='LinkedProduct',
            old_name='ultimo_recalculo',
            new_name='last_recalculated_at',
        ),
        migrations.RenameField(
            model_name='LinkedProduct',
            old_name='creado_en',
            new_name='created_at',
        ),
        migrations.RenameField(
            model_name='LinkedProduct',
            old_name='actualizado_en',
            new_name='updated_at',
        ),

        # ── Rename Fields: SupplierOrder (ex-PedidoProveedor) ────────────────

        migrations.RenameField(
            model_name='SupplierOrder',
            old_name='proveedor',
            new_name='supplier',
        ),
        migrations.RenameField(
            model_name='SupplierOrder',
            old_name='pedido_local',
            new_name='local_order',
        ),
        migrations.RenameField(
            model_name='SupplierOrder',
            old_name='proveedor_order_id',
            new_name='supplier_order_id',
        ),
        migrations.RenameField(
            model_name='SupplierOrder',
            old_name='estado',
            new_name='status',
        ),
        migrations.RenameField(
            model_name='SupplierOrder',
            old_name='moneda',
            new_name='currency',
        ),
        migrations.RenameField(
            model_name='SupplierOrder',
            old_name='payload_enviado',
            new_name='sent_payload',
        ),
        migrations.RenameField(
            model_name='SupplierOrder',
            old_name='respuesta_proveedor',
            new_name='supplier_response',
        ),
        migrations.RenameField(
            model_name='SupplierOrder',
            old_name='intentos',
            new_name='attempts',
        ),
        migrations.RenameField(
            model_name='SupplierOrder',
            old_name='fecha_creacion',
            new_name='created_at',
        ),
        migrations.RenameField(
            model_name='SupplierOrder',
            old_name='fecha_actualizacion',
            new_name='updated_at',
        ),

        # ── Rename Fields: SupplierTracking (ex-TrackingProveedor) ───────────

        migrations.RenameField(
            model_name='SupplierTracking',
            old_name='pedido',
            new_name='order',
        ),
        migrations.RenameField(
            model_name='SupplierTracking',
            old_name='proveedor_tracking_id',
            new_name='supplier_tracking_id',
        ),
        migrations.RenameField(
            model_name='SupplierTracking',
            old_name='numero_guia',
            new_name='tracking_number',
        ),
        migrations.RenameField(
            model_name='SupplierTracking',
            old_name='estado_envio',
            new_name='shipping_status',
        ),
        migrations.RenameField(
            model_name='SupplierTracking',
            old_name='transportadora',
            new_name='carrier',
        ),
        migrations.RenameField(
            model_name='SupplierTracking',
            old_name='historial_eventos',
            new_name='events_history',
        ),
        migrations.RenameField(
            model_name='SupplierTracking',
            old_name='url_tracking',
            new_name='tracking_url',
        ),
        migrations.RenameField(
            model_name='SupplierTracking',
            old_name='creado_en',
            new_name='created_at',
        ),
        migrations.RenameField(
            model_name='SupplierTracking',
            old_name='actualizado_en',
            new_name='updated_at',
        ),

        # ── Rename Fields: SupplierLog (ex-LogProveedor) ─────────────────────

        migrations.RenameField(
            model_name='SupplierLog',
            old_name='proveedor',
            new_name='supplier',
        ),
        migrations.RenameField(
            model_name='SupplierLog',
            old_name='tipo_evento',
            new_name='event_type',
        ),
        migrations.RenameField(
            model_name='SupplierLog',
            old_name='respuesta',
            new_name='response',
        ),
        migrations.RenameField(
            model_name='SupplierLog',
            old_name='estado',
            new_name='status',
        ),
        migrations.RenameField(
            model_name='SupplierLog',
            old_name='mensaje',
            new_name='message',
        ),
    ]
