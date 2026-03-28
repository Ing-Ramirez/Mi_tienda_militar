"""
Proveedores — Panel de Administración

Todos los modelos se registran en admin_site (FranjaAdminSite con TOTP),
nunca en admin.site por defecto.

SupplierLog es de solo lectura — auditoría inmutable.
"""
import json
from decimal import Decimal

from django import forms
from django.contrib import admin
from django.shortcuts import get_object_or_404, redirect
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.text import slugify

from core.admin_site import admin_site
from products.models import Category
from .http import proveedor_session
from .services.normalizacion import ServicioNormalizacion
from .models import (
    Supplier, SupplierProduct, SupplierVariant,
    LinkedProduct, SupplierOrder, SupplierTracking, SupplierLog,
    VariantStatus,
)

# ── Forms ───────────────────────────────────────────────────────────────────

class SupplierAdminForm(forms.ModelForm):
    credenciales = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 6}),
        help_text='JSON en claro (se cifrará con Fernet). Ej: {"token": "…"} o {"api_key":"…"}',
    )

    class Meta:
        model = Supplier
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Mostrar el JSON descifrado al editar, sin exponer el cifrado interno.
        if self.instance and getattr(self.instance, 'pk', None):
            try:
                self.fields['credenciales'].initial = json.dumps(
                    self.instance.credenciales or {}, ensure_ascii=False, indent=2
                )
            except Exception:
                self.fields['credenciales'].initial = ''

    def clean_credenciales(self):
        raw = (self.cleaned_data.get('credenciales') or '').strip()
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except Exception as exc:
            raise forms.ValidationError(f'JSON inválido en credenciales: {exc}')


# ── Helpers internos ────────────────────────────────────────────────────────

def _importar_variantes_desde_api(sup_prod: SupplierProduct) -> tuple[int, int]:
    """
    Llama a la API del proveedor y crea/actualiza SupplierVariant para este producto.
    Retorna (creadas, actualizadas).
    """
    supplier = sup_prod.supplier
    # usar la propiedad .credenciales que descifra Fernet — nunca _credentials directo
    creds    = supplier.credenciales
    token    = creds.get('token') or creds.get('api_key', '')
    if not token:
        raise ValueError(
            f'El proveedor "{supplier.name}" no tiene credenciales configuradas '
            f'o no se pudieron descifrar. Verifica el campo _credentials en el proveedor.'
        )
    headers  = {'Authorization': f'Bearer {token}'}

    session = proveedor_session()
    resp = session.get(
        f'{supplier.endpoint_base}/products/{sup_prod.supplier_product_id}',
        headers=headers,
        timeout=20,
    )
    resp.raise_for_status()
    data      = resp.json()
    result    = data.get('result', data)
    variants  = result.get('variants', [])
    normalizador = ServicioNormalizacion()
    creadas = actualizadas = 0
    for v in variants:
        in_stock  = v.get('in_stock', True)
        precio    = Decimal(str(v.get('price', '0')))
        calc_price = normalizador._aplicar_politica(precio, supplier.pricing_policy)
        _, created = SupplierVariant.objects.update_or_create(
            supplier_product    = sup_prod,
            supplier_variant_id = str(v['id']),
            defaults={
                'sku':               v.get('sku', ''),
                'base_price':        precio,
                'calculated_price':  calc_price,
                'attributes': {
                    'color': v.get('color', ''),
                    'size':  v.get('size', 'OS'),
                    'name':  v.get('name', ''),
                },
                'status': VariantStatus.ACTIVO if in_stock else VariantStatus.AGOTADO,
                'stock':  999 if in_stock else 0,
            },
        )
        if created:
            creadas += 1
        else:
            actualizadas += 1
    return creadas, actualizadas


def _crear_producto_local(sup_prod: SupplierProduct):
    """
    Crea un products.Product borrador desde un SupplierProduct y crea todos
    los LinkedProduct para sus variantes activas.
    Retorna el producto creado.
    """
    from products.models import Product

    variantes = sup_prod.variantes.filter(status=VariantStatus.ACTIVO)

    # ── Detectar si el producto usa tallas ──────────────────────────────
    _TALLA_UNICA = {'os', 'one size', 'onesize', 'talla única', 'u', 'unica', ''}
    tallas_reales = set()
    for v in variantes:
        talla = str(
            (v.attributes or {}).get('size') or
            (v.attributes or {}).get('talla', '')
        ).strip().lower()
        if talla not in _TALLA_UNICA:
            tallas_reales.add(talla)
    usa_tallas = len(tallas_reales) > 0

    # Precio base = mínimo de los precios calculados (precio más accesible)
    precios = [v.calculated_price for v in variantes if v.calculated_price]
    precio_base = min(precios) if precios else Decimal('0')

    # Slug único
    base_slug = slugify(sup_prod.name)[:48]
    slug = base_slug
    n = 1
    while Product.objects.filter(slug=slug).exists():
        slug = f'{base_slug}-{n}'
        n += 1

    # SKU único
    base_sku = f'PROV-{sup_prod.supplier_product_id}'[:20]
    sku = base_sku
    i = 1
    while Product.objects.filter(sku=sku).exists():
        sku = f'{base_sku}-{i}'
        i += 1

    local_prod = Product.objects.create(
        name              = sup_prod.name,
        slug              = slug,
        sku               = sku,
        description       = sup_prod.description,
        short_description = (sup_prod.description or '')[:250],
        category          = sup_prod.local_category,
        price             = precio_base,
        status            = 'inactive',
        stock             = 0,
        requires_size     = usa_tallas,
    )

    sup_prod.local_product = local_prod
    sup_prod.save(update_fields=['local_product'])

    for variante in variantes:
        LinkedProduct.objects.get_or_create(
            supplier_variant = variante,
            local_product    = local_prod,
            defaults={'max_stock': 10, 'is_active': True, 'sync_enabled': True},
        )

    from proveedores.services.stock_dinamico import ServicioStockDinamico
    motor = ServicioStockDinamico()
    for variante in variantes:
        motor.propagar_desde_variante(variante)

    return local_prod


# ── Inlines ────────────────────────────────────────────────────────────────

class SupplierVariantInline(admin.TabularInline):
    model         = SupplierVariant
    extra         = 0
    readonly_fields = [
        'supplier_variant_id', 'sku', 'base_price',
        'calculated_price', 'stock', 'atributos_legibles', 'updated_at',
    ]
    fields        = [
        'status',                           # editable: activo/agotado/inactivo
        'supplier_variant_id', 'sku',
        'atributos_legibles',               # color + talla legibles
        'base_price', 'calculated_price', 'stock',
    ]
    can_delete    = False
    verbose_name        = 'Variante del proveedor'
    verbose_name_plural = 'Variantes — elige cuáles activar antes de importar a tu tienda'

    def has_add_permission(self, request, obj=None):
        return False

    def atributos_legibles(self, obj):
        attrs = obj.attributes or {}
        color = attrs.get('color', '')
        talla = attrs.get('size') or attrs.get('talla', '')
        partes = [p for p in [color, talla] if p]
        return ' / '.join(partes) if partes else '—'
    atributos_legibles.short_description = 'Color / Talla'


class TrackingInline(admin.TabularInline):
    model         = SupplierTracking
    extra         = 0
    readonly_fields = [
        'tracking_number', 'carrier', 'shipping_status',
        'tracking_url', 'updated_at',
    ]
    fields        = readonly_fields
    can_delete    = False

    def has_add_permission(self, request, obj=None):
        return False


# ── Supplier ───────────────────────────────────────────────────────────────

@admin.register(Supplier, site=admin_site)
class SupplierAdmin(admin.ModelAdmin):
    form = SupplierAdminForm
    list_display  = [
        'name', 'slug', 'integration_type', 'adapter', 'status',
        'origin_currency', 'stock_buffer', 'created_at',
    ]
    list_filter   = ['status', 'integration_type', 'adapter']
    search_fields = ['name', 'slug']
    readonly_fields = ['id', 'created_at', 'updated_at']
    prepopulated_fields = {'slug': ('name',)}
    actions = ['action_sincronizar_catalogo']

    fieldsets = [
        ('Identificación', {
            'fields': ['id', 'name', 'slug', 'status', 'notes'],
        }),
        ('Integración', {
            'fields': [
                'integration_type', 'adapter', 'endpoint_base',
                'credenciales', 'webhook_secret',
            ],
            'description': (
                'Las credenciales se cifran con Fernet. Pega JSON en claro (se cifrará). '
                'Ej: {"api_key": "...", "token": "..."} o {"token":"..."}. '
                'Tipo «Simulación (mock)» + adaptador mock: sin HTTP (pruebas).'
            ),
        }),
        ('Precios e inventario', {
            'fields': ['pricing_policy', 'origin_currency', 'stock_buffer', 'delivery_days'],
        }),
        ('Fechas', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse'],
        }),
    ]

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                '<uuid:pk>/sincronizar-catalogo/',
                self.admin_site.admin_view(self._view_sincronizar_catalogo),
                name='proveedores_supplier_sincronizar_catalogo',
            ),
        ]
        return custom + urls

    def _supplier_change_url(self, pk):
        return reverse('admin:proveedores_supplier_change', args=[pk])

    def _view_sincronizar_catalogo(self, request, pk):
        proveedor = get_object_or_404(Supplier, pk=pk)
        try:
            from .services.sincronizacion import ServicioSincronizacion
            ServicioSincronizacion(proveedor).polling_completo()
            self.message_user(
                request,
                f'Sincronización iniciada y completada para "{proveedor.name}". '
                f'Revisa "Productos del proveedor" y "Logs" para ver resultados.',
            )
        except Exception as exc:
            self.message_user(
                request,
                f'Error sincronizando catálogo de "{proveedor.name}": {exc}',
                level='error',
            )
        return redirect(self._supplier_change_url(pk))

    @admin.action(description='Sincronizar catálogo ahora (polling REST/CSV) — seleccionados')
    def action_sincronizar_catalogo(self, request, queryset):
        from .services.sincronizacion import ServicioSincronizacion
        ok = err = 0
        for proveedor in queryset:
            try:
                ServicioSincronizacion(proveedor).polling_completo()
                ok += 1
            except Exception:
                err += 1
        msg = f'Sincronización completada para {ok} proveedor(es).'
        if err:
            msg += f'  |  {err} error(es) — revisa Logs del proveedor.'
        self.message_user(request, msg)

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        if obj and obj.pk:
            context['sincronizar_catalogo_url'] = reverse(
                'admin:proveedores_supplier_sincronizar_catalogo', args=[obj.pk]
            )
        return super().render_change_form(request, context, add, change, form_url, obj)

    def save_model(self, request, obj, form, change):
        # Aplicar cifrado desde el campo de formulario "credenciales".
        if 'credenciales' in form.cleaned_data:
            obj.credenciales = form.cleaned_data['credenciales']
        super().save_model(request, obj, form, change)


# ── SupplierProduct ─────────────────────────────────────────────────────────

@admin.register(SupplierProduct, site=admin_site)
class SupplierProductAdmin(admin.ModelAdmin):

    # ── Lista ───────────────────────────────────────────────────────────────
    list_display  = [
        'name', 'supplier', 'status',
        'local_category', 'variantes_badge', 'vinculo_badge', 'synced_at',
    ]
    list_filter   = ['status', 'supplier', 'local_category']
    search_fields = ['name', 'supplier_product_id']
    actions       = ['action_importar_variantes', 'action_importar_a_tienda']

    # ── Detalle ─────────────────────────────────────────────────────────────
    readonly_fields = [
        'id', 'supplier_product_id', 'category_name',
        'raw_data', 'synced_at', 'created_at',
        'panel_acciones',          # panel de botones en la ficha
    ]
    inlines             = [SupplierVariantInline]
    # Solo local_product: el buscador AJAX (nombre/SKU). local_category usa select
    # con todas las categorías activas — el autocomplete parecía «vacío» si no se escribe.
    autocomplete_fields = ['local_product']

    fieldsets = [
        ('Acciones rápidas', {
            'fields': ['panel_acciones'],
        }),
        ('Identificación', {
            'fields': ['id', 'supplier', 'supplier_product_id', 'status'],
        }),
        ('Contenido normalizado', {
            'fields': ['name', 'description'],
            'description': 'Edita aquí el nombre y descripción que verá el cliente.',
        }),
        ('Clasificación', {
            'fields': ['local_category', 'category_name'],
            'description': (
                'Categoría en tu tienda: elige una opción del desplegable (categorías activas). '
                'Categoría del proveedor: texto original del proveedor, solo lectura.'
            ),
        }),
        ('Vínculo local', {
            'fields': ['local_product'],
            'description': (
                'Opcional hasta que importes a la tienda. Para crear producto borrador y vínculos de stock '
                'usa «Importar a mi tienda» en Acciones rápidas (tras elegir categoría). '
                'Si ya tienes un producto local, búscalo escribiendo nombre o SKU en el campo.'
            ),
        }),
        ('Auditoría', {
            'fields': ['raw_data', 'synced_at', 'created_at'],
            'classes': ['collapse'],
        }),
    ]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'local_category':
            kwargs['queryset'] = Category.objects.filter(is_active=True).order_by(
                'order', 'name'
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    # ── Badges en la lista ──────────────────────────────────────────────────

    def variantes_badge(self, obj):
        n = obj.variantes.count()
        color = '#27ae60' if n > 0 else '#e74c3c'
        label = f'{n} variante{"s" if n != 1 else ""}' if n else 'Sin variantes'
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:10px;font-size:0.8em;font-weight:bold">{}</span>',
            color, label,
        )
    variantes_badge.short_description = 'Variantes'

    def vinculo_badge(self, obj):
        if obj.local_product_id:
            url = reverse('admin:products_product_change', args=[obj.local_product_id])
            return format_html(
                '<a href="{}" style="background:#2980b9;color:#fff;padding:2px 8px;'
                'border-radius:10px;font-size:0.8em;font-weight:bold;text-decoration:none">'
                'Ver en tienda</a>', url,
            )
        return format_html(
            '<span style="background:#95a5a6;color:#fff;padding:2px 8px;'
            'border-radius:10px;font-size:0.8em">Sin vincular</span>'
        )
    vinculo_badge.short_description = 'Catálogo propio'

    # ── Panel de acciones en la ficha (readonly_field con HTML) ─────────────

    def panel_acciones(self, obj):
        if not obj or not obj.pk:
            return 'Guarda el registro primero para ver las acciones disponibles.'

        n_variantes   = obj.variantes.count()
        tiene_local   = bool(obj.local_product_id)

        # URLs de las vistas personalizadas
        url_variantes = reverse(
            'admin:proveedores_supplierproduct_importar_variantes', args=[obj.pk]
        )
        url_tienda = reverse(
            'admin:proveedores_supplierproduct_importar_a_tienda', args=[obj.pk]
        )
        url_stock = reverse(
            'admin:proveedores_supplierproduct_sincronizar_stock', args=[obj.pk]
        )

        # Botón 1 — Importar / actualizar variantes (siempre disponible)
        btn_variantes = format_html(
            '<a href="{}" class="button" style="'
            'background:#417690;color:#fff;padding:7px 14px;'
            'text-decoration:none;border-radius:4px;margin-right:8px;display:inline-block">'
            'Importar variantes desde {}&nbsp;({})</a>',
            url_variantes, obj.supplier.name, n_variantes,
        )

        # Botón 2 — Importar a tienda (solo si no tiene local aún)
        tiene_categoria = bool(obj.local_category_id)
        if not tiene_local:
            if not tiene_categoria:
                btn_tienda = format_html(
                    '<span style="color:#c0392b;font-style:italic;font-size:0.85em">'
                    '⚠ Asigna primero la "Categoría en tu tienda" (sección Clasificación).</span>'
                )
            elif n_variantes > 0:
                btn_tienda = format_html(
                    '<a href="{}" class="button" style="'
                    'background:#1a7a1a;color:#fff;padding:7px 14px;'
                    'text-decoration:none;border-radius:4px;margin-right:8px;display:inline-block">'
                    'Importar a mi tienda (crear borrador)</a>',
                    url_tienda,
                )
            else:
                btn_tienda = format_html(
                    '<span style="color:#999;font-style:italic">'
                    'Importa variantes primero para poder crear el producto.</span>'
                )
        else:
            url_local = reverse('admin:products_product_change', args=[obj.local_product_id])
            btn_tienda = format_html(
                '<a href="{}" class="button" style="'
                'background:#2980b9;color:#fff;padding:7px 14px;'
                'text-decoration:none;border-radius:4px;margin-right:8px;display:inline-block">'
                'Ver / editar producto en tienda</a>',
                url_local,
            )

        # Botón 3 — Recalcular stock (solo si ya tiene vínculos)
        n_vinculos = LinkedProduct.objects.filter(
            supplier_variant__supplier_product=obj
        ).count()
        if n_vinculos > 0:
            btn_stock = format_html(
                '<a href="{}" class="button" style="'
                'background:#8e44ad;color:#fff;padding:7px 14px;'
                'text-decoration:none;border-radius:4px;display:inline-block">'
                'Recalcular stock ({} vínculo{})</a>',
                url_stock, n_vinculos, 's' if n_vinculos != 1 else '',
            )
        else:
            btn_stock = ''

        return format_html(
            '<div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center">'
            '{}{}{}</div>',
            btn_variantes, btn_tienda, btn_stock,
        )
    panel_acciones.short_description = 'Acciones disponibles'

    # ── URLs personalizadas ─────────────────────────────────────────────────

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                '<uuid:pk>/importar-variantes/',
                self.admin_site.admin_view(self._view_importar_variantes),
                name='proveedores_supplierproduct_importar_variantes',
            ),
            path(
                '<uuid:pk>/importar-a-tienda/',
                self.admin_site.admin_view(self._view_importar_a_tienda),
                name='proveedores_supplierproduct_importar_a_tienda',
            ),
            path(
                '<uuid:pk>/sincronizar-stock/',
                self.admin_site.admin_view(self._view_sincronizar_stock),
                name='proveedores_supplierproduct_sincronizar_stock',
            ),
        ]
        return custom + urls

    def _detalle_url(self, pk):
        return reverse('admin:proveedores_supplierproduct_change', args=[pk])

    # ── Vistas personalizadas ───────────────────────────────────────────────

    def _view_importar_variantes(self, request, pk):
        sup_prod = get_object_or_404(SupplierProduct, pk=pk)
        try:
            creadas, actualizadas = _importar_variantes_desde_api(sup_prod)
            self.message_user(
                request,
                f'Variantes importadas: {creadas} nuevas, {actualizadas} actualizadas '
                f'para "{sup_prod.name}".',
            )
        except Exception as exc:
            self.message_user(request, f'Error al importar variantes: {exc}', level='error')
        return redirect(self._detalle_url(pk))

    def _view_importar_a_tienda(self, request, pk):
        sup_prod = get_object_or_404(SupplierProduct, pk=pk)
        if sup_prod.local_product_id:
            self.message_user(
                request,
                'Este producto ya tiene un producto local vinculado.',
                level='warning',
            )
            return redirect(self._detalle_url(pk))
        if not sup_prod.local_category_id:
            self.message_user(
                request,
                'Asigna una "Categoría en tu tienda" antes de importar el producto.',
                level='error',
            )
            return redirect(self._detalle_url(pk))
        if not sup_prod.variantes.filter(status=VariantStatus.ACTIVO).exists():
            self.message_user(
                request,
                'Importa las variantes primero antes de crear el producto en tienda.',
                level='warning',
            )
            return redirect(self._detalle_url(pk))
        try:
            local_prod = _crear_producto_local(sup_prod)
            url_local  = reverse('admin:products_product_change', args=[local_prod.pk])
            self.message_user(
                request,
                format_html(
                    'Producto borrador creado: <a href="{}">{}</a>. '
                    'Ajusta precio, imágenes y slug antes de publicarlo.',
                    url_local, local_prod.name,
                ),
            )
        except Exception as exc:
            self.message_user(request, f'Error al crear el producto: {exc}', level='error')
        return redirect(self._detalle_url(pk))

    def _view_sincronizar_stock(self, request, pk):
        sup_prod  = get_object_or_404(SupplierProduct, pk=pk)
        vinculos  = LinkedProduct.objects.filter(
            supplier_variant__supplier_product=sup_prod
        ).select_related('supplier_variant', 'local_product')
        from proveedores.services.stock_dinamico import ServicioStockDinamico
        motor = ServicioStockDinamico()
        ok = 0
        for v in vinculos:
            try:
                motor.propagar_desde_variante(v.supplier_variant)
                ok += 1
            except Exception:
                pass
        self.message_user(request, f'Stock recalculado para {ok} vínculo(s) de "{sup_prod.name}".')
        return redirect(self._detalle_url(pk))

    # ── Actions de lista ────────────────────────────────────────────────────

    @admin.action(description='Importar variantes desde el proveedor (seleccionados)')
    def action_importar_variantes(self, request, queryset):
        ok = err = 0
        for sup_prod in queryset:
            try:
                c, a = _importar_variantes_desde_api(sup_prod)
                ok += 1
            except Exception:
                err += 1
        msg = f'{ok} producto(s) con variantes importadas.'
        if err:
            msg += f'  |  {err} error(es).'
        self.message_user(request, msg)

    @admin.action(description='Importar a mi tienda (crea borrador + vinculos de stock)')
    def action_importar_a_tienda(self, request, queryset):
        importados = omitidos = sin_variantes = sin_categoria = 0
        for sup_prod in queryset:
            if sup_prod.local_product_id:
                omitidos += 1
                continue
            if not sup_prod.local_category_id:
                sin_categoria += 1
                continue
            if not sup_prod.variantes.filter(status=VariantStatus.ACTIVO).exists():
                sin_variantes += 1
                continue
            try:
                _crear_producto_local(sup_prod)
                importados += 1
            except Exception:
                pass
        msgs = []
        if importados:
            msgs.append(f'{importados} producto(s) importado(s) como borrador.')
        if omitidos:
            msgs.append(f'{omitidos} ya tenían producto local.')
        if sin_categoria:
            msgs.append(f'{sin_categoria} sin categoría en tu tienda — asígnala primero.')
        if sin_variantes:
            msgs.append(f'{sin_variantes} sin variantes — importa variantes primero.')
        self.message_user(request, '  |  '.join(msgs) or 'Ningún producto procesado.')


# ── LinkedProduct ───────────────────────────────────────────────────────────

@admin.register(LinkedProduct, site=admin_site)
class LinkedProductAdmin(admin.ModelAdmin):
    list_display = [
        'supplier_variant', 'local_product',
        'stock_proveedor_display', 'max_stock', 'stock_visible_display',
        'is_active', 'sync_enabled', 'last_recalculated_at',
    ]
    list_filter  = ['is_active', 'sync_enabled', 'supplier_variant__supplier_product__supplier']
    search_fields = [
        'supplier_variant__sku', 'local_product__name',
        'supplier_variant__supplier_product__supplier__name',
    ]
    readonly_fields = ['id', 'aviso_flujo', 'calculated_stock', 'last_recalculated_at', 'created_at', 'updated_at']
    actions = ['recalcular_stock_seleccionados']

    def has_add_permission(self, request):
        # Los vínculos se crean exclusivamente desde el botón
        # "Importar a mi tienda" en el SupplierProduct.
        # Bloquear creación manual evita vínculos huérfanos.
        return False

    def aviso_flujo(self, obj):
        url = reverse('admin:proveedores_supplierproduct_changelist')
        return format_html(
            '<div style="background:#fffbeb;border-left:4px solid #f59e0b;'
            'padding:10px 14px;border-radius:6px;font-size:.87rem">'
            '<strong>¿Cómo crear vínculos?</strong><br>'
            'Ve al <a href="{}">Producto del proveedor</a>, importa las variantes '
            'y luego pulsa <em>"Importar a mi tienda"</em>. Ese botón crea '
            'automáticamente el producto en tu catálogo y todos sus vínculos de stock.'
            '</div>',
            url,
        )
    aviso_flujo.short_description = 'Información'

    fieldsets = [
        ('¿Cómo se crean los vínculos?', {
            'fields': ['aviso_flujo'],
        }),
        ('Vínculo', {
            'fields': ['id', 'supplier_variant', 'local_product'],
        }),
        ('Reglas de stock', {
            'fields': ['max_stock', 'calculated_stock', 'last_recalculated_at'],
            'description': 'Fórmula: stock_visible = min(stock_proveedor, max_stock)',
        }),
        ('Precio (override)', {
            'fields': ['price_margin'],
            'description': 'Deja vacío para usar la política del proveedor.',
            'classes': ['collapse'],
        }),
        ('Control', {
            'fields': ['is_active', 'sync_enabled'],
        }),
        ('Auditoría', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse'],
        }),
    ]

    def stock_proveedor_display(self, obj):
        stock = obj.supplier_variant.stock
        color = '#27ae60' if stock > 0 else '#e74c3c'
        return format_html('<span style="color:{};font-weight:bold">{}</span>', color, stock)
    stock_proveedor_display.short_description = 'Stock proveedor'

    def stock_visible_display(self, obj):
        visible = obj.stock_visible
        maximo  = obj.max_stock
        color   = '#27ae60' if visible > 0 else '#e74c3c'
        return format_html(
            '<span style="color:{};font-weight:bold">{}</span> / {}',
            color, visible, maximo,
        )
    stock_visible_display.short_description = 'Visible / Máx'

    @admin.action(description='Recalcular stock de los seleccionados')
    def recalcular_stock_seleccionados(self, request, queryset):
        from .services.stock_dinamico import ServicioStockDinamico
        motor = ServicioStockDinamico()
        ok = 0
        for vinculo in queryset.select_related('supplier_variant', 'local_product'):
            try:
                motor.recalcular(vinculo)
                ok += 1
            except Exception:
                pass
        self.message_user(request, f'{ok} vínculo(s) recalculados correctamente.')


# ── SupplierOrder ────────────────────────────────────────────────────────────

@admin.register(SupplierOrder, site=admin_site)
class SupplierOrderAdmin(admin.ModelAdmin):
    list_display  = [
        'local_order', 'supplier', 'status', 'total',
        'attempts', 'created_at',
    ]
    list_filter   = ['status', 'supplier']
    search_fields = ['supplier_order_id', 'local_order__order_number']
    readonly_fields = [
        'id', 'sent_payload', 'supplier_response',
        'attempts', 'created_at', 'updated_at',
    ]
    inlines = [TrackingInline]

    def has_delete_permission(self, request, obj=None):
        # Solo el superusuario puede eliminar pedidos al proveedor
        return request.user.is_superuser


# ── SupplierTracking ─────────────────────────────────────────────────────────

@admin.register(SupplierTracking, site=admin_site)
class SupplierTrackingAdmin(admin.ModelAdmin):
    list_display  = ['order', 'tracking_number', 'carrier', 'shipping_status', 'updated_at']
    list_filter   = ['carrier']
    search_fields = ['tracking_number', 'order__supplier_order_id']
    readonly_fields = [
        'id', 'order', 'supplier_tracking_id', 'tracking_number',
        'carrier', 'shipping_status', 'tracking_url',
        'events_history', 'created_at', 'updated_at',
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


# ── SupplierLog — Solo lectura ───────────────────────────────────────────────

@admin.register(SupplierLog, site=admin_site)
class SupplierLogAdmin(admin.ModelAdmin):
    list_display  = ['event_type', 'supplier', 'estado_coloreado', 'mensaje_corto', 'timestamp']
    list_filter   = ['event_type', 'status', 'supplier']
    search_fields = ['message']
    readonly_fields = ['id', 'event_type', 'supplier', 'payload', 'response', 'status', 'message', 'timestamp']

    def estado_coloreado(self, obj):
        colores = {'ok': '#27ae60', 'error': '#e74c3c', 'rechazado': '#e67e22'}
        color = colores.get(obj.status, '#7f8c8d')
        return format_html(
            '<span style="color:{};font-weight:bold">{}</span>',
            color, obj.get_status_display() if hasattr(obj, 'get_status_display') else obj.status,
        )
    estado_coloreado.short_description = 'Estado'

    def mensaje_corto(self, obj):
        return obj.message[:80] + ('…' if len(obj.message) > 80 else '')
    mensaje_corto.short_description = 'Mensaje'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
