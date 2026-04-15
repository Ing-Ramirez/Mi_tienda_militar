"""
Integración: checkout legacy / Neki, verificación de pago y despacho a proveedores.

Ejecutar:
  docker compose exec backend python manage.py test proveedores.tests.test_integration_proveedores_orders

Usa SQLite en memoria (override_settings) para no depender de PostgreSQL.
"""
from __future__ import annotations

import base64
import secrets
import shutil
import tempfile
from decimal import Decimal
from unittest.mock import MagicMock, patch

from cryptography.fernet import Fernet
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from orders.models import Cart, CartItem, ManualPaymentStatus, Order
from orders.services import create_order_neki_from_cart, create_order_from_cart
from products.models import Category, Product
from proveedores.models import (
    ProviderAdapter,
    SupplierStatus,
    SupplierOrder,
    SupplierProduct,
    LinkedProduct,
    Supplier,
    IntegrationType,
    SupplierVariant,
)
from proveedores.services.pedidos import ServicioPedidos
from users.models import User

# Checkout JSON legacy (sin comprobante; ya no dispara proveedores hasta verificación Neki)
LEGACY_CHECKOUT_URL = '/api/v1/orders/orders/checkout/'
# Checkout Neki (multipart)
NEKI_CHECKOUT_URL = '/api/v1/orders/checkout/'

_MIN_PNG = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
)

_TEST_USER_PASSWORD = secrets.token_urlsafe(16)


def _set_encryption_key() -> None:
    settings.ENCRYPTION_KEY = Fernet.generate_key().decode()


@override_settings(
    SECRET_KEY='integration-test-secret-not-for-production',
    DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        }
    },
)
class ProveedoresOrdersCheckoutIntegrationTests(TestCase):
    """Checkout legacy no envía a proveedores (flujo dropshipping tras pago verificado)."""

    def setUp(self):
        _set_encryption_key()

        self.user = User.objects.create_user(
            username='buyer1',
            email='buyer@example.com',
            password=_TEST_USER_PASSWORD,
        )
        self.cat = Category.objects.create(name='Cat', slug='cat-int')
        self.product = Product.objects.create(
            sku='LOC-SKU-001',
            name='Chaleco táctico',
            slug='chaleco-int',
            description='Test',
            category=self.cat,
            price=Decimal('100000.00'),
            requires_size=False,
            stock=50,
            status='active',
        )
        self.proveedor = Supplier.objects.create(
            name='Proveedor Test',
            slug='prov-test',
            integration_type=IntegrationType.API_REST,
            status=SupplierStatus.ACTIVO,
            endpoint_base='https://api.proveedor.test/v1/',
            adapter=ProviderAdapter.REST_GENERICO,
        )
        self.proveedor.credenciales = {'api_key': 'token-test'}
        self.proveedor.save()

        pp = SupplierProduct.objects.create(
            supplier=self.proveedor,
            supplier_product_id='EXT-P1',
            name='Chaleco proveedor',
            description='',
        )
        self.vp = SupplierVariant.objects.create(
            supplier_product=pp,
            supplier_variant_id='VAR-777',
            sku='LOC-SKU-001',
            base_price=Decimal('80000.00'),
            calculated_price=Decimal('100000.00'),
            stock=100,
        )
        LinkedProduct.objects.create(
            supplier_variant=self.vp,
            local_product=self.product,
            max_stock=20,
            is_active=True,
            sync_enabled=True,
        )

        self.cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            variant=None,
            talla='',
            quantity=2,
            price_at_addition=self.product.price,
        )

    @patch('proveedores.tasks.enviar_pedido_a_proveedor.delay')
    def test_legacy_checkout_no_despacha_a_proveedores(self, mock_delay: MagicMock):
        client = APIClient()
        client.force_authenticate(user=self.user)

        payload = {
            'email': 'ship@example.com',
            'shipping_full_name': 'Juan Pérez',
            'shipping_phone': '3001234567',
            'shipping_department': 'Cundinamarca',
            'shipping_city': 'Bogotá',
            'shipping_address_line1': 'Calle 1 # 2-3',
        }
        response = client.post(LEGACY_CHECKOUT_URL, payload, format='json')

        self.assertEqual(response.status_code, 201, getattr(response, 'data', response.content))
        order = Order.objects.get(order_number=response.data['order_number'])
        self.assertEqual(order.items.count(), 1)
        self.assertFalse(SupplierOrder.objects.filter(local_order=order).exists())
        mock_delay.assert_not_called()

    @patch('proveedores.tasks.enviar_pedido_a_proveedor.delay')
    def test_legacy_sin_vinculo_sin_pedido_proveedor(self, mock_delay: MagicMock):
        LinkedProduct.objects.all().delete()

        client = APIClient()
        client.force_authenticate(user=self.user)
        response = client.post(
            LEGACY_CHECKOUT_URL,
            {
                'email': 'a@b.co',
                'shipping_full_name': 'X',
                'shipping_phone': '1',
                'shipping_department': 'A',
                'shipping_city': 'B',
                'shipping_address_line1': 'C',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        order = Order.objects.get(order_number=response.data['order_number'])
        self.assertFalse(SupplierOrder.objects.filter(local_order=order).exists())
        mock_delay.assert_not_called()

    @patch('proveedores.tasks.enviar_pedido_a_proveedor.delay')
    def test_legacy_dos_proveedores_sin_despacho(self, mock_delay: MagicMock):
        prov_b = Supplier.objects.create(
            name='Proveedor B',
            slug='prov-b',
            integration_type=IntegrationType.API_REST,
            status=SupplierStatus.ACTIVO,
            endpoint_base='https://b.test/api/',
        )
        prov_b.credenciales = {'api_key': 'kb'}
        prov_b.save()
        prod_b = Product.objects.create(
            sku='SKU-B',
            name='Producto B',
            slug='prod-b',
            description='d',
            category=self.cat,
            price=Decimal('30000'),
            stock=20,
            status='active',
        )
        pp_b = SupplierProduct.objects.create(
            supplier=prov_b,
            supplier_product_id='PB1',
            name='PB',
        )
        vp_b = SupplierVariant.objects.create(
            supplier_product=pp_b,
            supplier_variant_id='VB-1',
            sku='SKU-B',
            base_price=Decimal('1'),
            calculated_price=Decimal('30000'),
            stock=10,
        )
        LinkedProduct.objects.create(
            supplier_variant=vp_b,
            local_product=prod_b,
        )
        CartItem.objects.create(
            cart=self.cart,
            product=prod_b,
            quantity=1,
            price_at_addition=prod_b.price,
        )

        client = APIClient()
        client.force_authenticate(user=self.user)
        response = client.post(
            LEGACY_CHECKOUT_URL,
            {
                'email': 'mix@example.com',
                'shipping_full_name': 'Mix',
                'shipping_phone': '2',
                'shipping_department': 'D',
                'shipping_city': 'C',
                'shipping_address_line1': 'Dir',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        order = Order.objects.get(order_number=response.data['order_number'])
        self.assertEqual(order.items.count(), 2)
        self.assertEqual(SupplierOrder.objects.filter(local_order=order).count(), 0)
        mock_delay.assert_not_called()


@override_settings(
    SECRET_KEY='integration-test-secret-not-for-production',
    DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        }
    },
)
class CreateOrderFromCartNoDespachoTests(TestCase):
    """create_order_from_cart no dispara envío a proveedores."""

    def setUp(self):
        _set_encryption_key()

        self.user = User.objects.create_user(
            username='u2',
            email='u2@example.com',
            password=_TEST_USER_PASSWORD,
        )
        cat = Category.objects.create(name='C2', slug='c2')
        product = Product.objects.create(
            sku='P2',
            name='P2',
            slug='p2',
            description='d',
            category=cat,
            price=Decimal('50000'),
            stock=10,
            status='active',
        )
        prov = Supplier.objects.create(
            name='P2',
            slug='p2',
            integration_type=IntegrationType.API_REST,
            status=SupplierStatus.ACTIVO,
            endpoint_base='https://x.test/api/',
        )
        prov.credenciales = {'api_key': 'k'}
        prov.save()
        pprod = SupplierProduct.objects.create(
            supplier=prov,
            supplier_product_id='1',
            name='n',
        )
        vp = SupplierVariant.objects.create(
            supplier_product=pprod,
            supplier_variant_id='v1',
            sku='P2',
            base_price=Decimal('1'),
            calculated_price=Decimal('50000'),
            stock=5,
        )
        LinkedProduct.objects.create(
            supplier_variant=vp,
            local_product=product,
        )
        self.cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(
            cart=self.cart,
            product=product,
            quantity=1,
            price_at_addition=product.price,
        )

    @patch('proveedores.tasks.enviar_pedido_a_proveedor.delay')
    def test_create_order_from_cart_sin_delay(self, mock_delay: MagicMock):
        order = create_order_from_cart(
            self.cart,
            self.user,
            {
                'email': 'e@e.co',
                'shipping_full_name': 'N',
                'shipping_phone': '1',
                'shipping_department': 'D',
                'shipping_city': 'C',
                'shipping_address_line1': 'A',
            },
        )
        self.assertTrue(Order.objects.filter(pk=order.pk).exists())
        self.assertEqual(SupplierOrder.objects.filter(local_order=order).count(), 0)
        mock_delay.assert_not_called()


@override_settings(
    SECRET_KEY='integration-test-secret-not-for-production',
    DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        }
    },
)
class ServicioPedidosHTTPIntegrationTests(TestCase):
    """ServicioPedidos + adaptador REST con requests mockeado."""

    def setUp(self):
        _set_encryption_key()

        self.user = User.objects.create_user(
            username='u3',
            email='u3@example.com',
            password=_TEST_USER_PASSWORD,
        )
        cat = Category.objects.create(name='C3', slug='c3')
        self.product = Product.objects.create(
            sku='SKU3',
            name='N3',
            slug='n3',
            description='d',
            category=cat,
            price=Decimal('75000'),
            stock=5,
            status='active',
        )
        self.proveedor = Supplier.objects.create(
            name='API',
            slug='api',
            integration_type=IntegrationType.API_REST,
            status=SupplierStatus.ACTIVO,
            endpoint_base='https://dropship.example/v1',
        )
        self.proveedor.credenciales = {'api_key': 'abc'}
        self.proveedor.save()

        pprod = SupplierProduct.objects.create(
            supplier=self.proveedor,
            supplier_product_id='pid',
            name='n',
        )
        vp = SupplierVariant.objects.create(
            supplier_product=pprod,
            supplier_variant_id='ext-var-99',
            sku='SKU3',
            base_price=Decimal('1'),
            calculated_price=Decimal('75000'),
            stock=3,
        )
        LinkedProduct.objects.create(
            supplier_variant=vp,
            local_product=self.product,
        )

        self.order = Order.objects.create(
            user=self.user,
            email='c@cliente.co',
            shipping_full_name='Cliente',
            shipping_phone='1',
            shipping_country='Colombia',
            shipping_department='Antioquia',
            shipping_city='Medellín',
            shipping_address_line1='Cra 1',
            subtotal=Decimal('75000'),
            shipping_cost=Decimal('0'),
            tax_amount=Decimal('0'),
            total=Decimal('75000'),
        )
        self.order.items.create(
            product=self.product,
            product_name=self.product.name,
            product_sku=self.product.sku,
            quantity=1,
            unit_price=Decimal('75000'),
            line_total=Decimal('75000'),
        )

    @patch('proveedores.services.adapters.rest_generico.requests.post')
    def test_enviar_a_proveedor_post_json_y_actualiza_estado(self, mock_post: MagicMock):
        mock_resp = MagicMock()
        mock_resp.content = b'{"order_id": "EXT-555"}'
        mock_resp.json.return_value = {'order_id': 'EXT-555'}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        svc = ServicioPedidos()
        pp = svc.crear_pedido_proveedor(self.order, self.proveedor, total=Decimal('75000'))
        ok = svc.enviar_a_proveedor(pp)

        self.assertTrue(ok)
        pp.refresh_from_db()
        self.assertEqual(pp.status, 'enviado')
        self.assertEqual(pp.supplier_order_id, 'EXT-555')
        self.assertEqual(pp.attempts, 1)

        mock_post.assert_called_once()
        call_kw = mock_post.call_args
        self.assertIn('json', call_kw.kwargs)
        body = call_kw.kwargs['json']
        self.assertEqual(body['referencia_interna'], self.order.order_number)
        arts = body['articulos']
        self.assertEqual(len(arts), 1)
        self.assertEqual(arts[0]['proveedor_variant_id'], 'ext-var-99')
        self.assertEqual(arts[0]['sku'], 'SKU3')
        self.assertEqual(mock_post.call_args[0][0], 'https://dropship.example/v1/orders/')

    def test_enviar_mock_sin_http(self):
        self.proveedor.integration_type = IntegrationType.MOCK
        self.proveedor.adapter = ProviderAdapter.MOCK
        self.proveedor.endpoint_base = ''
        self.proveedor.save()

        svc = ServicioPedidos()
        pp = svc.crear_pedido_proveedor(self.order, self.proveedor, total=Decimal('75000'))
        ok = svc.enviar_a_proveedor(pp)
        self.assertTrue(ok)
        pp.refresh_from_db()
        self.assertEqual(pp.status, 'enviado')
        self.assertTrue(pp.supplier_order_id.startswith('MOCK-'))


@override_settings(
    SECRET_KEY='integration-test-secret-not-for-production',
    DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        }
    },
)
class NekiCheckoutAndVerifyTests(TestCase):
    """POST /checkout/ Neki + señal VERIFIED → Celery send_order_to_provider."""

    def setUp(self):
        _set_encryption_key()
        self._media = tempfile.mkdtemp()
        settings.MEDIA_ROOT = self._media

        self.user = User.objects.create_user(
            username='nk',
            email='nk@example.com',
            password=_TEST_USER_PASSWORD,
        )
        cat = Category.objects.create(name='Nc', slug='nc')
        self.product = Product.objects.create(
            sku='NK1',
            name='P',
            slug='nk1',
            description='d',
            category=cat,
            price=Decimal('10000'),
            stock=5,
            status='active',
        )
        prov = Supplier.objects.create(
            name='Mock',
            slug='mock-p',
            integration_type=IntegrationType.MOCK,
            adapter=ProviderAdapter.MOCK,
            status=SupplierStatus.ACTIVO,
            endpoint_base='',
        )
        prov.credenciales = {}
        prov.save()
        pp = SupplierProduct.objects.create(
            supplier=prov,
            supplier_product_id='x',
            name='n',
        )
        vp = SupplierVariant.objects.create(
            supplier_product=pp,
            supplier_variant_id='ext1',
            sku='NK1',
            base_price=Decimal('1'),
            calculated_price=Decimal('10000'),
            stock=3,
        )
        LinkedProduct.objects.create(supplier_variant=vp, local_product=self.product)
        self.cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            quantity=1,
            price_at_addition=self.product.price,
        )

    def tearDown(self):
        shutil.rmtree(self._media, ignore_errors=True)

    def test_neki_post_crea_pending_sin_dispatch_task(self):
        client = APIClient()
        client.force_authenticate(user=self.user)
        with patch('orders.tasks.send_order_to_provider.delay') as mock_send:
            response = client.post(
                NEKI_CHECKOUT_URL,
                {
                    'email': 'e@e.co',
                    'shipping_full_name': 'N',
                    'shipping_phone': '1',
                    'shipping_department': 'D',
                    'shipping_city': 'C',
                    'shipping_address_line1': 'A',
                    'payment_proof': SimpleUploadedFile(
                        'p.png', _MIN_PNG, content_type='image/png'
                    ),
                },
                format='multipart',
            )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['manual_payment_status'], ManualPaymentStatus.PENDING)
        mock_send.assert_not_called()
        order = Order.objects.get(order_number=response.data['order_number'])
        self.assertTrue(order.payment_proof.name)
        self.assertEqual(SupplierOrder.objects.filter(local_order=order).count(), 0)

    @patch('orders.tasks.send_order_to_provider.delay')
    def test_marca_verified_encola_send_order(self, mock_send: MagicMock):
        proof = SimpleUploadedFile('p.png', _MIN_PNG, content_type='image/png')
        order = create_order_neki_from_cart(
            cart=self.cart,
            user=self.user,
            shipping_data={
                'email': 'e@e.co',
                'shipping_full_name': 'N',
                'shipping_phone': '1',
                'shipping_department': 'D',
                'shipping_city': 'C',
                'shipping_address_line1': 'A',
            },
            payment_proof=proof,
        )
        mock_send.reset_mock()
        order.manual_payment_status = ManualPaymentStatus.VERIFIED
        order.save()
        mock_send.assert_called_once_with(str(order.id))
        order.refresh_from_db()
        self.assertIsNotNone(order.providers_dispatch_enqueued_at)
