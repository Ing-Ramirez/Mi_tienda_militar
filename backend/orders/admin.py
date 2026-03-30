import logging
from django.contrib import admin
from django.utils.html import format_html
from .models import Cart, CartItem, Address, Order, OrderItem, Coupon
from core.admin_site import admin_site

logger = logging.getLogger(__name__)


# ── Inlines ──────────────────────────────────────────────────────────────────

class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = ('line_total',)
    verbose_name = 'Ítem'
    verbose_name_plural = 'Ítems del carrito'


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('line_total',)
    verbose_name = 'Ítem'
    verbose_name_plural = 'Ítems del pedido'


# ── Carrito ───────────────────────────────────────────────────────────────────

@admin.register(Cart, site=admin_site)
class CartAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'session_key', 'total_items', 'subtotal_display', 'updated_at')
    inlines = [CartItemInline]
    readonly_fields = ('created_at', 'updated_at')
    search_fields = ('user__email', 'session_key')

    def subtotal_display(self, obj):
        try:
            return format_html('<strong>${:,.0f}</strong>', float(obj.subtotal))
        except Exception as e:
            logger.warning('subtotal_display error carrito %s: %s', getattr(obj, 'pk', '?'), e)
            return '—'
    subtotal_display.short_description = 'Subtotal (COP)'


# ── Dirección ─────────────────────────────────────────────────────────────────

@admin.register(Address, site=admin_site)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'user', 'city', 'department', 'is_default')
    search_fields = ('full_name', 'user__email', 'city')
    list_filter = ('department', 'is_default')


# ── Pedidos ───────────────────────────────────────────────────────────────────

@admin.register(Order, site=admin_site)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'order_number', 'email', 'total_display',
        'status_badge', 'payment_badge', 'manual_payment_badge',
        'payment_method', 'created_at',
    )
    list_filter = ('status', 'payment_status', 'payment_method', 'manual_payment_status')
    search_fields = ('order_number', 'email', 'shipping_full_name')
    readonly_fields = (
        'order_number', 'created_at', 'updated_at',
        'payment_proof_preview', 'providers_dispatch_enqueued_at',
    )
    inlines = [OrderItemInline]
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Información del pedido', {
            'fields': (
                'order_number', 'user', 'email', 'status',
                'payment_status', 'payment_method', 'payment_id', 'coupon_code',
                'manual_payment_status', 'providers_dispatch_enqueued_at',
            ),
        }),
        ('Comprobante Nequi', {
            'fields': ('payment_proof', 'payment_proof_preview'),
            'classes': ('wide',),
        }),
        ('Totales (COP)', {
            'fields': ('subtotal', 'shipping_cost', 'tax_amount', 'discount_amount', 'total')
        }),
        ('Dirección de envío', {
            'fields': ('shipping_full_name', 'shipping_phone', 'shipping_country',
                       'shipping_department', 'shipping_city', 'shipping_address_line1',
                       'shipping_address_line2', 'shipping_postal_code',
                       'tracking_number', 'shipped_at', 'delivered_at')
        }),
        ('Notas', {
            'fields': ('customer_notes', 'internal_notes'),
            'classes': ('collapse',)
        }),
        ('Fechas', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def total_display(self, obj):
        try:
            return format_html('<strong>${:,.0f}</strong>', float(obj.total))
        except Exception as e:
            logger.warning('total_display error pedido %s: %s', getattr(obj, 'pk', '?'), e)
            return '—'
    total_display.short_description = 'Total (COP)'

    def status_badge(self, obj):
        try:
            colors = {
                'pending':    '#c9a227',
                'confirmed':  '#4a7c3f',
                'processing': '#2472a4',
                'shipped':    '#6c3483',
                'delivered':  '#1e8449',
                'cancelled':  '#b83232',
                'refunded':   '#888',
            }
            labels = {
                'pending':    '⏳ Pendiente',
                'confirmed':  '✅ Confirmado',
                'processing': '⚙️ En proceso',
                'shipped':    '🚚 Enviado',
                'delivered':  '📦 Entregado',
                'cancelled':  '❌ Cancelado',
                'refunded':   '↩️ Reembolsado',
            }
            return format_html(
                '<span style="background:{};color:white;padding:3px 10px;border-radius:3px;font-size:0.85em">{}</span>',
                colors.get(obj.status, '#888'),
                labels.get(obj.status, obj.status)
            )
        except Exception as e:
            logger.warning('status_badge error pedido %s: %s', getattr(obj, 'pk', '?'), e)
            return obj.status
    status_badge.short_description = 'Estado'

    def payment_badge(self, obj):
        try:
            colors = {
                'pending':  '#c9a227',
                'paid':     '#4a7c3f',
                'failed':   '#b83232',
                'refunded': '#888',
            }
            labels = {
                'pending':  '⏳ Pendiente',
                'paid':     '💳 Pagado',
                'failed':   '❌ Fallido',
                'refunded': '↩️ Reembolsado',
            }
            return format_html(
                '<span style="background:{};color:white;padding:3px 10px;border-radius:3px;font-size:0.85em">{}</span>',
                colors.get(obj.payment_status, '#888'),
                labels.get(obj.payment_status, obj.payment_status)
            )
        except Exception as e:
            logger.warning('payment_badge error pedido %s: %s', getattr(obj, 'pk', '?'), e)
            return obj.payment_status
    payment_badge.short_description = 'Pago'

    def manual_payment_badge(self, obj):
        if not obj.manual_payment_status:
            return '—'
        colors = {
            'PENDING':  '#c9a227',
            'PAID':     '#2472a4',
            'VERIFIED': '#1e8449',
            'REJECTED': '#b83232',
        }
        return format_html(
            '<span style="background:{};color:white;padding:3px 10px;border-radius:3px;font-size:0.85em">{}</span>',
            colors.get(obj.manual_payment_status, '#888'),
            obj.get_manual_payment_status_display()
            if hasattr(obj, 'get_manual_payment_status_display')
            else obj.manual_payment_status,
        )
    manual_payment_badge.short_description = 'Comprobante'

    def payment_proof_preview(self, obj):
        if not obj.payment_proof:
            return '—'
        url = obj.payment_proof.url
        return format_html(
            '<a href="{}" target="_blank" rel="noopener" title="Ver imagen completa">'
            '<div style="width:320px;height:320px;background:#1a1a1a;border:1px solid #444;'
            'border-radius:6px;overflow:hidden;display:flex;align-items:center;justify-content:center;">'
            '<img src="{}" style="width:100%;height:100%;object-fit:contain;" alt="Comprobante"/>'
            '</div></a>',
            url, url,
        )
    payment_proof_preview.short_description = 'Vista previa'


# ── Cupones ───────────────────────────────────────────────────────────────────

@admin.register(Coupon, site=admin_site)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_type', 'discount_value', 'uses_count',
                    'max_uses', 'valid_from', 'valid_until', 'is_active')
    list_filter = ('discount_type', 'is_active')
    search_fields = ('code',)
    list_editable = ('is_active',)
