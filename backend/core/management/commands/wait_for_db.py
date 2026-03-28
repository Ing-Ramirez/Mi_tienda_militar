"""
Comando: wait_for_db
Espera hasta que PostgreSQL esté disponible antes de iniciar Django.
Usado en docker-compose como primer paso del startup.
"""
import time
from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError


class Command(BaseCommand):
    help = 'Espera hasta que la base de datos esté disponible.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--max-retries', type=int, default=30,
            help='Número máximo de intentos (default: 30)'
        )
        parser.add_argument(
            '--interval', type=float, default=2.0,
            help='Segundos entre intentos (default: 2)'
        )

    def handle(self, *args, **options):
        max_retries = options['max_retries']
        interval = options['interval']
        db_conn = connections['default']

        self.stdout.write('Esperando conexion a la base de datos...')

        for attempt in range(1, max_retries + 1):
            try:
                db_conn.ensure_connection()
                self.stdout.write(
                    self.style.SUCCESS(f'Base de datos disponible (intento {attempt})')
                )
                return
            except OperationalError:
                self.stdout.write(f'  Intento {attempt}/{max_retries} — no disponible aun, esperando {interval}s...')
                time.sleep(interval)

        self.stderr.write(
            self.style.ERROR(f'No se pudo conectar a la base de datos despues de {max_retries} intentos.')
        )
        raise SystemExit(1)
