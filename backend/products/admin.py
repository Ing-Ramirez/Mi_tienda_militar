"""
Franja Pixelada — Admin de Productos
Panel de administración personalizado para gestión de inventario
"""
import csv
import json
import logging
from django.contrib import admin
from django.utils.html import format_html
from django.http import HttpResponse
from django.urls import reverse
from .models import Category, Tag, Product, ProductImage, ProductVariant, ProductReview, ReviewEvidence, InventoryLog, Favorito
from core.admin_site import admin_site

logger = logging.getLogger(__name__)


# ── Inlines ─────────────────────────────────────────────────────────────────

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ['image', 'alt_text', 'is_primary', 'order', 'thumbnail']
    readonly_fields = ['thumbnail']
    verbose_name = 'Imagen'
    verbose_name_plural = 'Imágenes del producto'

    def thumbnail(self, obj):
        try:
            if obj.image:
                return format_html(
                    '<div style="width:64px;height:64px;overflow:hidden;border-radius:4px;'
                    'border:1px solid #dee2e6">'
                    '<img src="{}" style="width:100%;height:100%;object-fit:cover;display:block">'
                    '</div>',
                    obj.image.url
                )
        except Exception:
            pass
        return '—'
    thumbnail.short_description = 'Vista previa'


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1
    fields = ['variant_type', 'name', 'sku', 'size', 'color', 'color_hex',
              'price_adjustment', 'stock', 'is_active']
    verbose_name = 'Variante'
    verbose_name_plural = 'Variantes del producto'
    show_change_link = True


# ── Categorías ───────────────────────────────────────────────────────────────

@admin.register(Category, site=admin_site)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent', 'product_count', 'is_active', 'order']
    list_editable = ['is_active', 'order']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name', 'description']
    list_filter = ['is_active', 'parent']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Información general', {
            'fields': ('name', 'slug', 'description'),
        }),
        ('Multimedia', {
            'fields': ('image', 'icon'),
        }),
        ('Estructura', {
            'fields': ('parent',),
        }),
        ('Configuración', {
            'fields': ('is_active', 'order'),
        }),
        ('Fechas', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def product_count(self, obj):
        try:
            count = obj.products.filter(status='active').count()
            return format_html('<span class="fp-cat-count">{}</span>', count)
        except Exception:
            return '—'
    product_count.short_description = 'Productos activos'


# ── Etiquetas ────────────────────────────────────────────────────────────────

@admin.register(Tag, site=admin_site)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


# ── Productos ────────────────────────────────────────────────────────────────

@admin.register(Product, site=admin_site)
class ProductAdmin(admin.ModelAdmin):
    class Media:
        css = {'all': ('css/admin_productos.css',)}
        js = ('js/admin_productos.js',)

    list_display = [
        'thumbnail_preview', 'name', 'category',
        'price_display', 'stock_display', 'status_badge',
        'details_btn',
    ]
    list_editable = []
    list_filter = ['status', 'category', 'is_featured', 'is_new', 'personalization_type']
    search_fields = ['name', 'sku', 'description']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at', 'discount_info']
    inlines = [ProductImageInline, ProductVariantInline]
    save_on_top = True
    actions = ['activate_products', 'deactivate_products', 'export_inventory_csv']

    fieldsets = (
        ('Información general', {
            'fields': ('sku', 'name', 'slug', 'short_description', 'description',
                       'category', 'tags'),
            'description': 'Datos principales del producto visibles en la tienda.',
        }),
        ('Tallas e inventario', {
            'fields': ('requires_size', 'stock', 'stock_by_size', 'personalization_type',
                       'low_stock_threshold', 'track_inventory', 'weight'),
            'description': (
                'Si "Requiere talla" está activo: define el stock por talla — el total se calcula automáticamente. '
                'Si no: usa el campo "Stock" global directamente.'
            ),
        }),
        ('Precios (COP)', {
            'fields': ('price', 'compare_at_price', 'cost_price', 'discount_info'),
            'classes': ('wide',),
            'description': 'Precio de venta, precio anterior (tachado) y costo interno.',
        }),
        ('Estado y visibilidad', {
            'fields': ('status', 'is_featured', 'is_new'),
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description'),
            'description': 'Opcional. Mejora el posicionamiento en buscadores.',
        }),
        ('Fechas', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def thumbnail_preview(self, obj):
        try:
            img = obj.main_image
            if img and img.image:
                return format_html(
                    '<div class="fp-thumb-wrap">'
                    '<img src="{}" class="fp-thumb-img" alt="">'
                    '</div>',
                    img.image.url
                )
        except Exception:
            pass
        return format_html(
            '<div class="fp-thumb-wrap fp-thumb-empty">📦</div>'
        )
    thumbnail_preview.short_description = 'Imagen'

    def price_display(self, obj):
        try:
            price = f'${float(obj.price):,.0f}'
            if obj.compare_at_price:
                compare = f'${float(obj.compare_at_price):,.0f}'
                return format_html(
                    '<strong>{}</strong><br><s style="color:#888;font-size:0.8em">{}</s>',
                    price, compare
                )
            return format_html('<strong>{}</strong>', price)
        except (TypeError, ValueError) as e:
            logger.warning('price_display error para producto %s: %s', getattr(obj, 'pk', '?'), e)
            return '—'
    price_display.short_description = 'Precio'

    def stock_display(self, obj):
        try:
            if obj.stock == 0:
                color, label = '#b83232', f'⚠ Sin stock'
            elif obj.is_low_stock:
                color, label = '#c9a227', f'⚡ {obj.stock} (bajo)'
            else:
                color, label = '#4a7c3f', str(obj.stock)
            return format_html(
                '<span style="background:{};color:white;padding:3px 10px;border-radius:3px;font-weight:bold">{}</span>',
                color, label
            )
        except Exception as e:
            logger.warning('stock_display error para producto %s: %s', getattr(obj, 'pk', '?'), e)
            return '—'
    stock_display.short_description = 'Inventario'

    def status_badge(self, obj):
        try:
            colors = {
                'active':       '#4a7c3f',
                'inactive':     '#888',
                'out_of_stock': '#b83232',
                'coming_soon':  '#c9a227',
            }
            labels = {
                'active':       '✅ Activo',
                'inactive':     '⏸ Inactivo',
                'out_of_stock': '❌ Agotado',
                'coming_soon':  '🔜 Próximamente',
            }
            return format_html(
                '<span style="background:{};color:white;padding:3px 10px;border-radius:3px;font-size:0.85em">{}</span>',
                colors.get(obj.status, '#888'),
                labels.get(obj.status, obj.status)
            )
        except Exception as e:
            logger.warning('status_badge error para producto %s: %s', getattr(obj, 'pk', '?'), e)
            return '—'
    status_badge.short_description = 'Estado'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('category').prefetch_related('images')

    def details_btn(self, obj):
        try:
            images = []
            for img in obj.images.all().order_by('order', '-is_primary')[:12]:
                if img.image:
                    try:
                        images.append({'url': img.image.url, 'alt': img.alt_text or ''})
                    except Exception:
                        pass
            data = {
                'id':              str(obj.pk),
                'sku':             obj.sku or '',
                'name':            obj.name or '',
                'status':          obj.status or '',
                'category':        obj.category.name if obj.category else '—',
                'personalization': obj.get_personalization_type_display(),
                'is_featured':     obj.is_featured,
                'is_new':          obj.is_new,
                'updated_at':      obj.updated_at.strftime('%d/%m/%Y %H:%M') if obj.updated_at else '—',
                'price':           str(obj.price) if obj.price else '0',
                'compare_at_price': str(obj.compare_at_price) if obj.compare_at_price else '',
                'cost_price':      str(obj.cost_price) if obj.cost_price else '',
                'stock':           obj.stock,
                'description':     obj.description or '',
                'short_description': obj.short_description or '',
                'images':          images,
                'edit_url':        reverse('admin:products_product_change', args=[obj.pk]),
            }
            json_data = json.dumps(data, ensure_ascii=False)
            return format_html(
                '<button type="button" class="fp-detail-btn" data-product="{}">'
                'Detalles</button>',
                json_data,
            )
        except Exception as e:
            logger.warning('details_btn error for product %s: %s', getattr(obj, 'pk', '?'), e)
            return '—'
    details_btn.short_description = ''

    def discount_info(self, obj):
        try:
            if obj.discount_percentage:
                return format_html(
                    '<span style="color:#c9a227;font-weight:bold">{}% de descuento activo</span>',
                    obj.discount_percentage
                )
        except Exception:
            pass
        return '— Sin descuento'
    discount_info.short_description = 'Descuento'

    @admin.action(description='✅ Activar productos seleccionados')
    def activate_products(self, request, queryset):
        count = queryset.update(status='active')
        self.message_user(request, f'{count} producto(s) activado(s) correctamente.')

    @admin.action(description='⏸ Desactivar productos seleccionados')
    def deactivate_products(self, request, queryset):
        count = queryset.update(status='inactive')
        self.message_user(request, f'{count} producto(s) desactivado(s).')

    @admin.action(description='📥 Exportar inventario a CSV')
    def export_inventory_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="inventario_franja_pixelada.csv"'
        writer = csv.writer(response)
        writer.writerow(['SKU', 'Nombre', 'Categoría', 'Precio', 'Precio Anterior', 'Stock', 'Estado'])
        for p in queryset.select_related('category'):
            writer.writerow([
                p.sku, p.name,
                p.category.name if p.category else '',
                p.price, p.compare_at_price or '',
                p.stock, p.get_status_display()
            ])
        return response


# ── Variantes ────────────────────────────────────────────────────────────────

@admin.register(ProductVariant, site=admin_site)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ('product', 'variant_type', 'name', 'sku', 'stock', 'price_adjustment', 'is_active')
    list_filter = ('variant_type', 'is_active')
    search_fields = ('name', 'sku', 'product__name')


# ── Reseñas ──────────────────────────────────────────────────────────────────

class ReviewEvidenceInline(admin.TabularInline):
    model = ReviewEvidence
    extra = 0
    readonly_fields = ['thumb', 'uploaded_at']
    fields = ['thumb', 'uploaded_at']
    verbose_name = 'Imagen'
    verbose_name_plural = 'Imágenes de evidencia'

    def thumb(self, obj):
        if obj.image:
            try:
                return format_html(
                    '<a href="{}" target="_blank">'
                    '<img src="{}" style="width:80px;height:60px;object-fit:cover;border-radius:3px">'
                    '</a>', obj.image.url, obj.image.url
                )
            except Exception:
                pass
        return '—'
    thumb.short_description = 'Vista previa'

    def has_add_permission(self, request, obj=None):
        return False


STATUS_BADGE_COLORS = {
    'pending':  ('#c9a227', '⏳'),
    'approved': ('#4a7c3f', '✅'),
    'hidden':   ('#888',    '🙈'),
}


@admin.register(ProductReview, site=admin_site)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = [
        'product', 'user_email', 'rating_display', 'status_badge',
        'is_verified_purchase', 'order_link', 'created_at',
    ]
    list_filter = ['status', 'rating', 'is_verified_purchase', 'created_at']
    search_fields = ['product__name', 'user__email', 'comment', 'title']
    readonly_fields = ['id', 'user', 'product', 'order', 'is_verified_purchase',
                       'is_approved', 'created_at', 'updated_at']
    inlines = [ReviewEvidenceInline]
    actions = ['approve_reviews', 'hide_reviews', 'mark_pending']

    fieldsets = (
        ('Identificación', {
            'fields': ('id', 'user', 'product', 'order', 'is_verified_purchase'),
        }),
        ('Contenido', {
            'fields': ('rating', 'title', 'comment'),
        }),
        ('Moderación', {
            'fields': ('status', 'is_approved'),
        }),
        ('Fechas', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def user_email(self, obj):
        return obj.user.email if obj.user else '—'
    user_email.short_description = 'Cliente'

    def rating_display(self, obj):
        try:
            stars = '★' * obj.rating + '☆' * (5 - obj.rating)
            return format_html('<span style="color:#c9a227">{}</span> ({})', stars, obj.rating)
        except Exception:
            return obj.rating
    rating_display.short_description = 'Calificación'

    def status_badge(self, obj):
        color, icon = STATUS_BADGE_COLORS.get(obj.status, ('#888', '•'))
        label = obj.get_status_display()
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;border-radius:3px;font-size:0.82em">'
            '{} {}</span>', color, icon, label
        )
    status_badge.short_description = 'Estado'

    def order_link(self, obj):
        if obj.order:
            return format_html(
                '<span style="font-family:monospace">{}</span>',
                obj.order.order_number,
            )
        return '—'
    order_link.short_description = 'Pedido'

    def save_model(self, request, obj, form, change):
        """Sincronizar is_approved con status al guardar desde admin."""
        obj.is_approved = (obj.status == 'approved')
        super().save_model(request, obj, form, change)

    @admin.action(description='✅ Aprobar reseñas seleccionadas')
    def approve_reviews(self, request, queryset):
        count = queryset.update(status='approved', is_approved=True)
        self.message_user(request, f'{count} reseña(s) aprobada(s) y publicada(s).')

    @admin.action(description='🙈 Ocultar reseñas seleccionadas')
    def hide_reviews(self, request, queryset):
        count = queryset.update(status='hidden', is_approved=False)
        self.message_user(request, f'{count} reseña(s) ocultada(s).')

    @admin.action(description='⏳ Volver a pendiente')
    def mark_pending(self, request, queryset):
        count = queryset.update(status='pending', is_approved=False)
        self.message_user(request, f'{count} reseña(s) marcadas como pendientes.')


# ── Registro de inventario ───────────────────────────────────────────────────

@admin.register(InventoryLog, site=admin_site)
class InventoryLogAdmin(admin.ModelAdmin):
    list_display = ['product', 'action', 'quantity_change', 'stock_before', 'stock_after', 'created_by', 'created_at']
    list_filter = ['action', 'created_at']
    search_fields = ['product__name', 'product__sku']
    readonly_fields = ['product', 'variant', 'action', 'quantity_change',
                       'stock_before', 'stock_after', 'created_by', 'created_at']
    date_hierarchy = 'created_at'

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False


# ── Favoritos ────────────────────────────────────────────────────────────────

@admin.register(Favorito, site=admin_site)
class FavoritoAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'created_at')
    readonly_fields = ('created_at',)
