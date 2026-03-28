import logging
from django.contrib import admin
from django.utils.html import format_html
from .models import Payment
from core.admin_site import admin_site

logger = logging.getLogger(__name__)


@admin.register(Payment, site=admin_site)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('payment_id_short', 'order', 'method_display', 'amount_display',
                    'currency', 'status_badge', 'created_at')
    list_filter = ('method', 'status', 'currency')
    search_fields = ('payment_id', 'order__order_number')
    readonly_fields = ('created_at', 'updated_at', 'raw_response')
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Información del pago', {
            'fields': ('order', 'payment_id', 'method', 'status', 'currency', 'amount')
        }),
        ('Respuesta del proveedor', {
            'fields': ('raw_response',),
            'classes': ('collapse',)
        }),
        ('Fechas', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def has_add_permission(self, request):
        return False

    def payment_id_short(self, obj):
        try:
            pid = obj.payment_id or ''
            return pid[:20] + '…' if len(pid) > 20 else pid or '—'
        except Exception:
            return '—'
    payment_id_short.short_description = 'ID de pago'

    def amount_display(self, obj):
        try:
            return format_html('<strong>${:,.0f} {}</strong>', float(obj.amount), obj.currency)
        except (TypeError, ValueError) as e:
            logger.warning('amount_display error pago %s: %s', getattr(obj, 'pk', '?'), e)
            return '—'
    amount_display.short_description = 'Monto'

    def method_display(self, obj):
        icons = {'stripe': '💳 Stripe', 'paypal': '🅿️ PayPal', 'cash': '💵 Efectivo'}
        return icons.get(obj.method, obj.method)
    method_display.short_description = 'Método'

    def status_badge(self, obj):
        try:
            colors = {
                'pending':   '#c9a227',
                'completed': '#4a7c3f',
                'failed':    '#b83232',
                'refunded':  '#888',
            }
            labels = {
                'pending':   '⏳ Pendiente',
                'completed': '✅ Completado',
                'failed':    '❌ Fallido',
                'refunded':  '↩️ Reembolsado',
            }
            return format_html(
                '<span style="background:{};color:white;padding:3px 10px;border-radius:3px;font-size:0.85em">{}</span>',
                colors.get(obj.status, '#888'),
                labels.get(obj.status, obj.status)
            )
        except Exception as e:
            logger.warning('status_badge error pago %s: %s', getattr(obj, 'pk', '?'), e)
            return obj.status
    status_badge.short_description = 'Estado'
