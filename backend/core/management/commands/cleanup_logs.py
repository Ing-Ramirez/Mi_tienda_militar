"""
Comando: cleanup_logs
Aplica política de retención a logs de proveedores y payloads históricos de pagos.
"""
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from payments.models import Payment
from proveedores.models import SupplierLog


class Command(BaseCommand):
    help = 'Limpia logs antiguos según política de retención.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo muestra cuántos registros serían afectados.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        now = timezone.now()

        supplier_cutoff = now - timedelta(days=settings.SUPPLIER_LOG_RETENTION_DAYS)
        payment_cutoff = now - timedelta(days=settings.PAYMENT_LOG_RETENTION_DAYS)

        old_supplier_qs = SupplierLog.objects.filter(timestamp__lt=supplier_cutoff)
        old_payment_qs = Payment.objects.filter(created_at__lt=payment_cutoff).exclude(raw_response={})

        supplier_count = old_supplier_qs.count()
        payment_count = old_payment_qs.count()

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'[dry-run] SupplierLog a eliminar: {supplier_count}; '
                    f'Payment.raw_response a depurar: {payment_count}'
                )
            )
            return

        deleted_supplier = old_supplier_qs.delete()[0]
        cleaned_payments = old_payment_qs.update(raw_response={})

        self.stdout.write(
            self.style.SUCCESS(
                f'Limpieza completada. SupplierLog eliminados: {deleted_supplier}; '
                f'Payments depurados: {cleaned_payments}'
            )
        )
