from django.contrib import admin

from core.admin_site import admin_site
from .models import LoyaltyAccount, PointTransaction


@admin.register(LoyaltyAccount, site=admin_site)
class LoyaltyAccountAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'points_balance', 'total_earned', 'total_redeemed', 'updated_at',
    ]
    search_fields = ['user__email', 'user__first_name', 'user__last_name']
    readonly_fields = [
        'id', 'user', 'points_balance', 'total_earned',
        'total_redeemed', 'created_at', 'updated_at',
    ]

    def has_add_permission(self, request):
        return False  # Se crean automáticamente al primer acceso del usuario


@admin.register(PointTransaction, site=admin_site)
class PointTransactionAdmin(admin.ModelAdmin):
    list_display = [
        'created_at', 'account', 'transaction_type', 'points',
        'balance_after', 'order',
    ]
    list_filter = ['transaction_type']
    search_fields = ['account__user__email', 'order__order_number', 'description']
    date_hierarchy = 'created_at'
    readonly_fields = [
        'id', 'account', 'transaction_type', 'points',
        'balance_after', 'order', 'description', 'metadata', 'created_at',
    ]

    # Inmutable: prohibir crear, editar y eliminar desde el admin
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
