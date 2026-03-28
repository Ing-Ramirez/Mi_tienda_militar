from django.contrib import admin
from .models import LoginAttempt, AdminAuditLog
from .admin_site import admin_site


@admin.register(LoginAttempt, site=admin_site)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = ('username', 'ip_address', 'resultado', 'agente_corto', 'timestamp')
    list_filter = ('was_successful',)
    search_fields = ('username', 'ip_address')
    readonly_fields = ('id', 'username', 'ip_address', 'was_successful', 'user_agent', 'timestamp')
    ordering = ('-timestamp',)
    date_hierarchy = 'timestamp'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def resultado(self, obj):
        if obj.was_successful:
            return '✅ Exitoso'
        return '❌ Fallido'
    resultado.short_description = 'Resultado'

    def agente_corto(self, obj):
        try:
            ua = obj.user_agent or ''
            return ua[:60] + '…' if len(ua) > 60 else ua or '—'
        except Exception:
            return '—'
    agente_corto.short_description = 'Navegador / Agente'


@admin.register(AdminAuditLog, site=admin_site)
class AdminAuditLogAdmin(admin.ModelAdmin):
    list_display = ('admin_username', 'accion', 'model_name', 'object_repr', 'ip_address', 'timestamp')
    list_filter = ('action', 'model_name')
    search_fields = ('admin_username', 'object_repr', 'ip_address')
    readonly_fields = (
        'id', 'admin', 'admin_username', 'action', 'model_name',
        'object_id', 'object_repr', 'changes', 'ip_address', 'timestamp'
    )
    ordering = ('-timestamp',)
    date_hierarchy = 'timestamp'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def accion(self, obj):
        icons = {'create': '➕ Crear', 'update': '✏️ Editar', 'delete': '🗑️ Eliminar'}
        return icons.get(obj.action, obj.action)
    accion.short_description = 'Acción'
