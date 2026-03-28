from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User
from core.admin_site import admin_site


@admin.register(User, site=admin_site)
class UserAdmin(BaseUserAdmin):
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
            'fields': ('first_name', 'last_name', 'phone', 'birth_date')
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
