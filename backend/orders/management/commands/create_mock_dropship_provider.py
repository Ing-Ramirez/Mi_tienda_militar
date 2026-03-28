"""
Crea un proveedor dropshipping simulado (sin HTTP), útil con Neki + Celery en desarrollo.

  python manage.py create_mock_dropship_provider
"""
from django.core.management.base import BaseCommand

from proveedores.models import ProviderAdapter, SupplierStatus, Supplier, IntegrationType


class Command(BaseCommand):
    help = 'Crea el proveedor mock-dropship (tipo mock, adaptador mock).'

    def handle(self, *args, **options):
        slug = 'mock-dropship'
        if Supplier.objects.filter(slug=slug).exists():
            self.stdout.write(self.style.WARNING(f'Ya existe un proveedor con slug={slug}.'))
            return

        p = Supplier.objects.create(
            name='Proveedor simulado (pruebas)',
            slug=slug,
            integration_type=IntegrationType.MOCK,
            adapter=ProviderAdapter.MOCK,
            status=SupplierStatus.ACTIVO,
            endpoint_base='',
            pricing_policy={'tipo': 'margen', 'valor': 0},
        )
        p.credenciales = {}
        p.save()
        self.stdout.write(self.style.SUCCESS(f'Proveedor creado: {p.name} ({p.slug})'))
