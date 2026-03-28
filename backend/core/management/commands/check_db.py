"""
Comando: check_db
Verifica que la base de datos exista y contenga todas las tablas requeridas.
Si faltan tablas, ejecuta las migraciones automaticamente.
Ejecutar con: python manage.py check_db
"""
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.utils import OperationalError
from django.core.management import call_command

REQUIRED_TABLES = [
    # users
    'users_user',
    # products
    'products_category',
    'products_tag',
    'products_product',
    'products_productimage',
    'products_productvariant',
    'products_productreview',
    'products_inventorylog',
    'products_favorito',
    # orders
    'orders_cart',
    'orders_cartitem',
    'orders_address',
    'orders_order',
    'orders_orderitem',
    'orders_coupon',
    # payments
    'payments_payment',
]


class Command(BaseCommand):
    help = 'Verifica la base de datos y crea tablas faltantes automaticamente.'

    def handle(self, *args, **options):
        self.stdout.write('=' * 55)
        self.stdout.write('  Franja Pixelada — Verificacion de Base de Datos')
        self.stdout.write('=' * 55)

        # 1. Verificar conexion
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT version()')
                version = cursor.fetchone()[0]
            self.stdout.write(self.style.SUCCESS(f'[OK] Conexion exitosa'))
            self.stdout.write(f'     {version[:60]}')
        except OperationalError as e:
            self.stderr.write(self.style.ERROR(f'[ERROR] No se puede conectar: {e}'))
            raise SystemExit(1)

        # 2. Obtener tablas existentes
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
            """)
            existing = {row[0] for row in cursor.fetchall()}

        # 3. Verificar tablas requeridas
        missing = [t for t in REQUIRED_TABLES if t not in existing]

        if not missing:
            self.stdout.write(
                self.style.SUCCESS(
                    f'[OK] Todas las tablas existen ({len(REQUIRED_TABLES)} verificadas)'
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'[ADVERTENCIA] Faltan {len(missing)} tabla(s):')
            )
            for table in missing:
                self.stdout.write(f'     - {table}')
            self.stdout.write('\nEjecutando migraciones para crear tablas faltantes...')
            call_command('migrate', '--noinput', verbosity=1)
            self.stdout.write(self.style.SUCCESS('[OK] Migraciones completadas'))

        # 4. Resumen
        self.stdout.write('-' * 55)
        self.stdout.write('Tablas en la base de datos:')
        all_app_tables = sorted(t for t in existing if '_' in t and not t.startswith('django_') and not t.startswith('auth_'))
        for table in all_app_tables:
            status = '[OK]' if table in REQUIRED_TABLES else '    '
            self.stdout.write(f'  {status} {table}')
        self.stdout.write('=' * 55)
