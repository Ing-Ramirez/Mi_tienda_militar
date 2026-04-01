"""
Franja Pixelada — Admin de Devoluciones
"""
from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from django.urls import reverse

from core.admin_site import admin_site
from .models import ReturnRequest, ReturnItem, ReturnEvidence, ReturnAuditLog, VALID_TRANSITIONS


# ── Inlines ──────────────────────────────────────────────────────────────────

class ReturnItemInline(admin.TabularInline):
    model  = ReturnItem
    extra  = 0
    fields = ['order_item_link', 'quantity', 'condition', 'has_original_packaging']
    readonly_fields = ['order_item_link']
    verbose_name = 'Ítem'
    verbose_name_plural = 'Ítems a devolver'

    def order_item_link(self, obj):
        return format_html(
            '<strong>{}</strong><br><small style="color:#888">SKU: {}</small>',
            obj.order_item.product_name,
            obj.order_item.product_sku or '—',
        )
    order_item_link.short_description = 'Producto'

    def has_add_permission(self, request, obj=None):
        return False


class ReturnEvidenceInline(admin.TabularInline):
    model  = ReturnEvidence
    extra  = 0
    fields = ['thumb', 'caption', 'uploaded_at']
    readonly_fields = ['thumb', 'uploaded_at']
    verbose_name = 'Evidencia'
    verbose_name_plural = 'Evidencias del cliente'

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
    thumb.short_description = 'Imagen'

    def has_add_permission(self, request, obj=None):
        return False


class ReturnAuditLogInline(admin.TabularInline):
    model  = ReturnAuditLog
    extra  = 0
    fields = ['created_at', 'transition_display', 'changed_by', 'note']
    readonly_fields = ['created_at', 'transition_display', 'changed_by', 'note']
    verbose_name = 'Evento'
    verbose_name_plural = 'Historial de estados'

    def transition_display(self, obj):
        if not obj.from_status:
            return format_html('<span style="color:#4a7c3f">✦ Creada</span>')
        return format_html(
            '<span style="color:#888">{}</span> → <strong>{}</strong>',
            obj.get_from_status_display() if hasattr(obj, 'get_from_status_display') else obj.from_status,
            obj.to_status,
        )
    transition_display.short_description = 'Transición'

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# ── Admin principal ──────────────────────────────────────────────────────────

STATUS_COLORS = {
    'requested':  ('#c97a10', '⏳'),
    'reviewing':  ('#2878c8', '🔍'),
    'approved':   ('#4a7c3f', '✅'),
    'rejected_subsanable':  ('#d4a017', '⚠'),
    'rejected_definitive':  ('#666',    '⛔'),
    'in_transit': ('#8b4fc8', '📦'),
    'received':   ('#2878c8', '📥'),
    'validated':  ('#4a7c3f', '🔎'),
    'refunded':   ('#4a7c3f', '💰'),
    'closed':     ('#888',    '🔒'),
}


@admin.register(ReturnRequest, site=admin_site)
class ReturnRequestAdmin(admin.ModelAdmin):
    list_display  = [
        'short_id', 'return_code', 'user_email', 'order_link',
        'reason_short', 'status_badge', 'refund_status_badge',
        'refund_amount', 'requested_at',
    ]
    list_filter   = ['status', 'reason', 'refund_status', 'requested_at']
    search_fields = ['user__email', 'order__order_number', 'id']
    readonly_fields = [
        'id', 'user', 'order', 'parent_return', 'attempt_number',
        'rejection_reason', 'rejected_at',
        'requested_at', 'resolved_at',
        'refund_at', 'updated_at', 'transition_actions',
    ]
    inlines = [ReturnItemInline, ReturnEvidenceInline, ReturnAuditLogInline]
    save_on_top = True

    fieldsets = (
        ('Identificación', {
            'fields': ('id', 'user', 'order', 'parent_return', 'attempt_number', 'requested_at', 'resolved_at'),
        }),
        ('Motivo del cliente', {
            'fields': ('reason', 'reason_detail', 'customer_notes'),
        }),
        ('Rechazo (cliente + auditoría)', {
            'fields': ('rejection_reason', 'rejected_at', 'admin_notes'),
        }),
        ('Gestión interna', {
            'fields': ('status', 'transition_actions'),
        }),
        ('Reembolso', {
            'fields': ('refund_method', 'refund_status', 'refund_amount', 'refund_at'),
        }),
    )

    # ── Columnas del listado ─────────────────────────────────────────────────

    def short_id(self, obj):
        return str(obj.id)[:8].upper()
    short_id.short_description = 'ID'

    def user_email(self, obj):
        return obj.user.email if obj.user else '—'
    user_email.short_description = 'Cliente'

    def order_link(self, obj):
        url = reverse(f'{admin_site.name}:orders_order_change', args=[obj.order.pk])
        return format_html(
            '<a href="{}">{}</a>',
            url,
            obj.order.order_number,
        )
    order_link.short_description = 'Orden'

    def reason_short(self, obj):
        return obj.get_reason_display()
    reason_short.short_description = 'Motivo'

    def status_badge(self, obj):
        color, icon = STATUS_COLORS.get(obj.status, ('#888', '•'))
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;border-radius:3px;font-size:0.82em">'
            '{} {}</span>',
            color, icon, obj.get_status_display()
        )
    status_badge.short_description = 'Estado'

    def refund_status_badge(self, obj):
        colors = {
            'pending':   '#888',
            'partial':   '#c97a10',
            'full':      '#4a7c3f',
            'denied':    '#b83232',
            'processed': '#4a7c3f',
        }
        color = colors.get(obj.refund_status, '#888')
        return format_html(
            '<span style="color:{};font-weight:600">{}</span>',
            color, obj.get_refund_status_display()
        )
    refund_status_badge.short_description = 'Estado reembolso'

    # ── Campo de acciones de transición ─────────────────────────────────────

    def transition_actions(self, obj):
        nexts = VALID_TRANSITIONS.get(obj.status, [])
        if not nexts:
            return format_html('<span style="color:#888">Sin transiciones disponibles.</span>')
        from .models import STATUS_CHOICES
        labels = dict(STATUS_CHOICES)
        btn_styles = {
            'approved':   'background:#4a7c3f',
            'rejected_subsanable':  'background:#d4a017',
            'rejected_definitive': 'background:#8b2942',
            'refunded':   'background:#2878c8',
            'closed':     'background:#555',
        }
        buttons = []
        for s in nexts:
            style = btn_styles.get(s, 'background:#555')
            buttons.append(
                f'<a href="transition/?to={s}" '
                f'style="{style};color:#fff;padding:4px 12px;border-radius:3px;'
                f'text-decoration:none;font-size:0.82em;margin-right:6px;display:inline-block">'
                f'{labels.get(s, s)}</a>'
            )
        return format_html(''.join(buttons))
    transition_actions.short_description = 'Acciones de transición'

    # ── Acciones masivas ─────────────────────────────────────────────────────

    actions = [
        'mark_reviewing',
        'mark_approved',
        'mark_rejected_subsanable',
        'mark_rejected_definitive',
        'mark_received',
        'mark_validated',
        'mark_refunded',
        'mark_closed',
    ]

    @admin.action(description='🔍 Marcar como En revisión')
    def mark_reviewing(self, request, queryset):
        count = 0
        for obj in queryset:
            if obj.can_transition_to('reviewing'):
                obj.transition('reviewing', changed_by=request.user, note='Acción masiva admin.')
                count += 1
        self.message_user(request, f'{count} devolución(es) marcadas como En revisión.')

    @admin.action(description='✅ Aprobar seleccionadas')
    def mark_approved(self, request, queryset):
        count = 0
        for obj in queryset:
            if obj.can_transition_to('approved'):
                obj.transition('approved', changed_by=request.user, note='Aprobación masiva admin.')
                count += 1
        self.message_user(request, f'{count} devolución(es) aprobadas.')

    @admin.action(description='⚠ Rechazar como subsanable (reintento permitido)')
    def mark_rejected_subsanable(self, request, queryset):
        count = 0
        default_reason = 'Revisión administrativa: subsanable (completa el motivo en cada caso si aplica).'
        for obj in queryset:
            if obj.can_transition_to('rejected_subsanable'):
                obj.rejection_reason = default_reason
                obj.rejected_at = timezone.now()
                obj.refund_status = 'denied'
                obj.save(update_fields=['rejection_reason', 'rejected_at', 'refund_status'])
                obj.transition('rejected_subsanable', changed_by=request.user, note='Rechazo subsanable (acción masiva).')
                count += 1
        self.message_user(request, f'{count} devolución(es) marcadas como rechazo subsanable.')

    @admin.action(description='⛔ Rechazar como definitivo (sin reintento)')
    def mark_rejected_definitive(self, request, queryset):
        count = 0
        default_reason = 'Revisión administrativa: no procede devolución según políticas.'
        for obj in queryset:
            if obj.can_transition_to('rejected_definitive'):
                obj.rejection_reason = default_reason
                obj.rejected_at = timezone.now()
                obj.refund_status = 'denied'
                obj.save(update_fields=['rejection_reason', 'rejected_at', 'refund_status'])
                obj.transition('rejected_definitive', changed_by=request.user, note='Rechazo definitivo (acción masiva).')
                count += 1
        self.message_user(request, f'{count} devolución(es) marcadas como rechazo definitivo.')

    @admin.action(description='📥 Marcar como Recibida')
    def mark_received(self, request, queryset):
        count = 0
        for obj in queryset:
            if obj.can_transition_to('received'):
                obj.transition('received', changed_by=request.user, note='Recepción marcada desde admin.')
                count += 1
        self.message_user(request, f'{count} devolución(es) marcadas como recibidas.')

    @admin.action(description='🔎 Validar producto')
    def mark_validated(self, request, queryset):
        count = 0
        for obj in queryset:
            if obj.can_transition_to('validated'):
                obj.transition('validated', changed_by=request.user, note='Validación desde admin.')
                count += 1
        self.message_user(request, f'{count} devolución(es) validadas.')

    @admin.action(description='💰 Ejecutar reembolso')
    def mark_refunded(self, request, queryset):
        count = 0
        for obj in queryset:
            if obj.can_transition_to('refunded'):
                obj.transition('refunded', changed_by=request.user, note='Reembolso ejecutado desde admin.')
                count += 1
        self.message_user(request, f'{count} devolución(es) reembolsadas.')

    @admin.action(description='🔒 Cerrar seleccionadas')
    def mark_closed(self, request, queryset):
        count = 0
        for obj in queryset:
            if obj.can_transition_to('closed'):
                obj.transition('closed', changed_by=request.user, note='Cierre masivo admin.')
                count += 1
        self.message_user(request, f'{count} devolución(es) cerradas.')

    def has_delete_permission(self, request, obj=None):
        return False
