"""
Comando: setup_roles
Crea los tres grupos de roles de Franja Pixelada con sus permisos.

Uso:
    python manage.py setup_roles

Roles creados:
    1. SuperAdministrador  — Control total
    2. AdministradorTienda — Productos, precios, stock, pedidos
    3. GestorInventario    — Stock e imágenes solamente
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType


ROLES = {
    'SuperAdministrador': {
        'description': 'Control total del sistema. Puede gestionar usuarios, pagos y seguridad.',
        'apps_permissions': '__all__',
    },
    'AdministradorTienda': {
        'description': 'Gestiona productos, precios, stock y pedidos. Sin acceso a usuarios ni seguridad.',
        'codenames': [
            # products
            'view_product', 'add_product', 'change_product',
            'view_category', 'add_category', 'change_category',
            'view_productimage', 'add_productimage', 'change_productimage', 'delete_productimage',
            'view_productvariant', 'add_productvariant', 'change_productvariant',
            'view_inventorylog', 'add_inventorylog',
            'view_tag', 'add_tag', 'change_tag',
            'view_productreview', 'change_productreview', 'delete_productreview',
            # orders
            'view_order', 'change_order',
            'view_orderitem',
            'view_cart',
            'view_address',
            'view_coupon', 'add_coupon', 'change_coupon',
            # payments
            'view_payment',
            # audit (solo lectura)
            'view_adminauditlog',
        ],
    },
    'GestorInventario': {
        'description': 'Actualiza stock e imágenes. Sin acceso a pagos, pedidos ni usuarios.',
        'codenames': [
            'view_product', 'change_product',
            'view_productimage', 'add_productimage', 'change_productimage', 'delete_productimage',
            'view_productvariant', 'add_productvariant', 'change_productvariant',
            'view_inventorylog', 'add_inventorylog',
            'view_category',
        ],
    },
}


class Command(BaseCommand):
    help = 'Crea los grupos de roles (SuperAdministrador, AdministradorTienda, GestorInventario).'

    def handle(self, *args, **options):
        self.stdout.write('=' * 55)
        self.stdout.write('  Franja Pixelada — Configuración de Roles')
        self.stdout.write('=' * 55)

        for role_name, config in ROLES.items():
            group, created = Group.objects.get_or_create(name=role_name)
            action = 'creado' if created else 'actualizado'

            if config.get('apps_permissions') == '__all__':
                # SuperAdministrador: todos los permisos
                perms = Permission.objects.all()
                group.permissions.set(perms)
                self.stdout.write(
                    self.style.SUCCESS(f'[OK] {role_name} {action} — todos los permisos')
                )
            else:
                codenames = config.get('codenames', [])
                perms = Permission.objects.filter(codename__in=codenames)
                group.permissions.set(perms)
                found = perms.count()
                self.stdout.write(
                    self.style.SUCCESS(
                        f'[OK] {role_name} {action} — {found}/{len(codenames)} permisos asignados'
                    )
                )
                if found < len(codenames):
                    missing = set(codenames) - set(perms.values_list('codename', flat=True))
                    for m in sorted(missing):
                        self.stdout.write(self.style.WARNING(f'     Permiso no encontrado: {m}'))

        self.stdout.write('=' * 55)
        self.stdout.write(
            self.style.SUCCESS(
                'Roles listos. Asigna usuarios desde el admin: '
                f'Usuarios > editar usuario > Grupos'
            )
        )
