from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib import messages
from django.utils.translation import ngettext
from core.middleware import _get_client_ip
from core.models import AdminAuditLog
from .models import User
from .forms import UserAdminForm
from core.admin_site import admin_site


@admin.register(User, site=admin_site)
class UserAdmin(BaseUserAdmin):
    form = UserAdminForm

    class Media:
        css = {'all': ['css/fp_user_permissions.css', 'css/fp_admin_users.css']}
        js = ['js/fp_user_permissions.js', 'js/fp_admin_users.js']
    list_display = (
        'email',
        'nombre_display',
        'apellido_display',
        'phone',
        'rol_display',
        'estado_display',
        'created_at',
    )
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'two_factor_enabled')
    search_fields = ('email', 'first_name', 'last_name', 'document_number')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at', 'last_login', 'date_joined')

    fieldsets = (
        ('Credenciales', {
            'fields': ('email', 'username', 'password')
        }),
        ('Información personal', {
            'fields': ('first_name', 'last_name', 'phone', 'birth_date', 'profile_image')
        }),
        ('Documento de identidad', {
            'fields': ('document_type', 'document_number'),
        }),
        ('Seguridad', {
            'fields': ('two_factor_enabled', 'phone_2fa'),
        }),
        ('Permisos', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',),
        }),
        ('Preferencias', {
            'fields': ('accepts_marketing',),
        }),
        ('Fechas', {
            'fields': ('last_login', 'date_joined', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    add_fieldsets = (
        ('Cuenta nueva', {
            'classes': ('wide',),
            'fields': ('email', 'username', 'first_name', 'last_name', 'password1', 'password2'),
        }),
    )
    actions = ('activate_users', 'deactivate_users')

    def rol_display(self, obj):
        if obj.is_superuser:
            return '🔴 Superadmin'
        if obj.is_staff:
            return '🟡 Staff'
        return '🟢 Cliente'
    rol_display.short_description = 'Rol'

    def nombre_display(self, obj):
        return obj.first_name
    nombre_display.short_description = 'Nombre'

    def apellido_display(self, obj):
        return obj.last_name
    apellido_display.short_description = 'Apellido'

    def estado_display(self, obj):
        return 'Activo' if obj.is_active else 'Inactivo'
    estado_display.short_description = 'Estado'

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        labels = {
            'username': 'Usuario',
            'first_name': 'Nombre',
            'last_name': 'Apellido',
            'is_staff': 'Acceso al panel',
            'is_superuser': 'Superusuario',
            'last_login': 'Ultimo acceso',
            'date_joined': 'Fecha de registro',
            'groups': 'Grupos',
            'user_permissions': 'Permisos',
        }
        for field_name, label in labels.items():
            if field_name in form.base_fields:
                form.base_fields[field_name].label = label
        return form

    def changelist_view(self, request, extra_context=None):
        self.message_user(
            request,
            'Aviso: la opción de 2FA por SMS aún no está implementada en el flujo de login.',
            level=messages.WARNING,
        )
        return super().changelist_view(request, extra_context=extra_context)

    def _build_changes_map(self, form):
        return {
            field: [form.initial.get(field), form.cleaned_data.get(field)]
            for field in form.changed_data
        }

    def _log_admin_action(self, request, obj, action, changes=None):
        AdminAuditLog.objects.create(
            admin=request.user,
            admin_username=getattr(request.user, 'email', '') or getattr(request.user, 'username', ''),
            action=action,
            model_name='User',
            object_id=str(obj.pk),
            object_repr=str(obj),
            changes=changes or {},
            ip_address=_get_client_ip(request),
        )

    def save_model(self, request, obj, form, change):
        changes = self._build_changes_map(form) if change else {}
        super().save_model(request, obj, form, change)
        self._log_admin_action(
            request=request,
            obj=obj,
            action='update' if change else 'create',
            changes=changes,
        )

    def delete_model(self, request, obj):
        object_pk = obj.pk
        object_repr = str(obj)
        super().delete_model(request, obj)
        AdminAuditLog.objects.create(
            admin=request.user,
            admin_username=getattr(request.user, 'email', '') or getattr(request.user, 'username', ''),
            action='delete',
            model_name='User',
            object_id=str(object_pk),
            object_repr=object_repr,
            changes={},
            ip_address=_get_client_ip(request),
        )

    @admin.action(description='Activar usuarios seleccionados')
    def activate_users(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(
            request,
            ngettext(
                '%d usuario activado correctamente.',
                '%d usuarios activados correctamente.',
                updated,
            ) % updated,
        )

    @admin.action(description='Desactivar usuarios seleccionados')
    def deactivate_users(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            ngettext(
                '%d usuario desactivado correctamente.',
                '%d usuarios desactivados correctamente.',
                updated,
            ) % updated,
        )
