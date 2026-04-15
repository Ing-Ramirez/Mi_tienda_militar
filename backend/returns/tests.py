from datetime import timedelta
from decimal import Decimal
import secrets

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from orders.models import Order, OrderItem
from products.models import Category, Product
from returns.models import ReturnRequest


User = get_user_model()


class ReturnsFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        pw_user = secrets.token_urlsafe(16)
        pw_admin = secrets.token_urlsafe(16)
        self.user = User.objects.create_user(
            username='return_user',
            email='return_user@example.com',
            password=pw_user,
        )
        self.admin = User.objects.create_superuser(
            username='admin_return',
            email='admin_return@example.com',
            password=pw_admin,
        )
        self.category = Category.objects.create(name='Accesorios', slug='accesorios')
        self.product = Product.objects.create(
            sku='RET-001',
            name='Guantes tácticos',
            slug='guantes-tacticos',
            description='Producto para pruebas de devolución',
            category=self.category,
            price=Decimal('85000.00'),
            requires_size=False,
            stock=20,
            status='active',
        )
        self.order = Order.objects.create(
            user=self.user,
            email=self.user.email,
            shipping_full_name='Usuario Retorno',
            shipping_phone='3000000000',
            shipping_country='Colombia',
            shipping_department='Bogotá D.C.',
            shipping_city='Bogotá',
            shipping_address_line1='Calle 123 #45-67',
            subtotal=Decimal('85000.00'),
            shipping_cost=Decimal('0.00'),
            tax_amount=Decimal('16150.00'),
            total=Decimal('101150.00'),
            status='delivered',
            payment_status='paid',
            delivered_at=timezone.now() - timedelta(days=3),
        )
        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            product_sku=self.product.sku,
            quantity=1,
            unit_price=Decimal('85000.00'),
            line_total=Decimal('85000.00'),
        )

    def test_create_return_request_success(self):
        self.client.force_authenticate(user=self.user)
        payload = {
            'order_id': str(self.order.id),
            'reason': 'defective',
            'reason_detail': 'Costura abierta en el dedo índice',
            'customer_notes': 'Solicito cambio o reembolso.',
            'refund_method': 'original',
            'items': [
                {
                    'order_item_id': str(self.order_item.id),
                    'quantity': 1,
                    'condition': 'unused',
                    'has_original_packaging': True,
                }
            ],
        }
        res = self.client.post('/api/v1/returns/', payload, format='json')
        self.assertEqual(res.status_code, 201)
        self.assertEqual(ReturnRequest.objects.count(), 1)
        rr = ReturnRequest.objects.first()
        self.assertEqual(rr.status, 'requested')
        self.assertTrue(rr.return_code.startswith('DEV-'))

    def test_prevent_duplicate_returns_while_active(self):
        ReturnRequest.objects.create(user=self.user, order=self.order, reason='regret')
        self.client.force_authenticate(user=self.user)
        res = self.client.get(f'/api/v1/returns/eligibility/{self.order.id}/')
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.json().get('eligible'))

    def test_allow_new_return_after_rejection_subsanable_with_parent(self):
        rr = ReturnRequest.objects.create(user=self.user, order=self.order, reason='regret')
        self.client.force_authenticate(user=self.admin)
        endpoint = f'/api/v1/returns/{rr.id}/transition/'
        res = self.client.post(
            endpoint,
            {
                'status': 'rejected_subsanable',
                'rejection_reason': 'Falta el empaque original del producto.',
                'admin_notes': 'Nota interna',
                'note': 'Revisión',
            },
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        rr.refresh_from_db()
        self.assertEqual(rr.status, 'rejected_subsanable')
        self.assertIn('empaque', rr.rejection_reason.lower())

        self.client.force_authenticate(user=self.user)
        el = self.client.get(f'/api/v1/returns/eligibility/{self.order.id}/')
        self.assertEqual(el.status_code, 200)
        body = el.json()
        self.assertFalse(body.get('eligible'), body)
        self.assertIn('intenta', (body.get('reason') or '').lower())

        payload = {
            'parent_return_id': str(rr.id),
            'order_id': str(self.order.id),
            'reason': 'defective',
            'reason_detail': 'Segundo intento',
            'items': [
                {
                    'order_item_id': str(self.order_item.id),
                    'quantity': 1,
                    'condition': 'unused',
                    'has_original_packaging': True,
                }
            ],
        }
        res2 = self.client.post('/api/v1/returns/', payload, format='json')
        self.assertEqual(res2.status_code, 201, res2.json())
        self.assertEqual(ReturnRequest.objects.filter(order=self.order).count(), 2)
        rr.refresh_from_db()
        self.assertEqual(rr.status, 'closed')

    def test_rejection_definitive_blocks_new_attempt(self):
        rr = ReturnRequest.objects.create(user=self.user, order=self.order, reason='regret')
        self.client.force_authenticate(user=self.admin)
        endpoint = f'/api/v1/returns/{rr.id}/transition/'
        res = self.client.post(
            endpoint,
            {
                'status': 'rejected_definitive',
                'rejection_reason': 'Producto fuera del plazo de devolución.',
                'note': 'Cierre',
            },
            format='json',
        )
        self.assertEqual(res.status_code, 200)

        self.client.force_authenticate(user=self.user)
        el = self.client.get(f'/api/v1/returns/eligibility/{self.order.id}/')
        self.assertFalse(el.json().get('eligible'))
        payload = {
            'parent_return_id': str(rr.id),
            'order_id': str(self.order.id),
            'reason': 'defective',
            'items': [
                {
                    'order_item_id': str(self.order_item.id),
                    'quantity': 1,
                    'condition': 'unused',
                    'has_original_packaging': True,
                }
            ],
        }
        res2 = self.client.post('/api/v1/returns/', payload, format='json')
        self.assertEqual(res2.status_code, 400)

    @override_settings(RETURN_MAX_ATTEMPTS_PER_ORDER=2)
    def test_max_attempts_per_order(self):
        self.client.force_authenticate(user=self.user)
        base_payload = {
            'order_id': str(self.order.id),
            'reason': 'regret',
            'items': [
                {
                    'order_item_id': str(self.order_item.id),
                    'quantity': 1,
                    'condition': 'unused',
                    'has_original_packaging': True,
                }
            ],
        }
        r1 = ReturnRequest.objects.create(user=self.user, order=self.order, reason='regret')
        self.client.force_authenticate(user=self.admin)
        e = f'/api/v1/returns/{r1.id}/transition/'
        self.client.post(
            e,
            {'status': 'rejected_subsanable', 'rejection_reason': 'Subsanable uno.'},
            format='json',
        )
        self.client.force_authenticate(user=self.user)
        p2 = dict(base_payload, parent_return_id=str(r1.id))
        self.assertEqual(self.client.post('/api/v1/returns/', p2, format='json').status_code, 201)
        r1.refresh_from_db()
        self.assertEqual(r1.status, 'closed')
        r2 = ReturnRequest.objects.filter(order=self.order).exclude(pk=r1.pk).first()
        self.client.force_authenticate(user=self.admin)
        self.client.post(
            f'/api/v1/returns/{r2.id}/transition/',
            {'status': 'rejected_subsanable', 'rejection_reason': 'Subsanable dos.'},
            format='json',
        )
        self.client.force_authenticate(user=self.user)
        p3 = dict(base_payload, parent_return_id=str(r2.id))
        res = self.client.post('/api/v1/returns/', p3, format='json')
        self.assertEqual(res.status_code, 400)

    def test_transition_flow_admin(self):
        rr = ReturnRequest.objects.create(user=self.user, order=self.order, reason='regret')
        self.client.force_authenticate(user=self.admin)
        endpoint = f'/api/v1/returns/{rr.id}/transition/'
        self.assertEqual(self.client.post(endpoint, {'status': 'reviewing'}, format='json').status_code, 200)
        self.assertEqual(self.client.post(endpoint, {'status': 'approved'}, format='json').status_code, 200)
        rr.refresh_from_db()
        self.assertIsNotNone(rr.shipping_deadline_at)

    def test_return_policy_endpoint(self):
        res = self.client.get('/api/v1/returns/policy/')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('window_days_new', data)
        self.assertIn('shipment_window_days', data)
        self.assertIn('document', data)
        self.assertIn('sections', data['document'])
        self.assertTrue(isinstance(data['document']['sections'], list))

    def test_list_returns_authenticated(self):
        rr = ReturnRequest.objects.create(
            user=self.user,
            order=self.order,
            reason='incomplete',
            reason_detail='Falta un accesorio',
        )
        self.client.force_authenticate(user=self.user)
        res = self.client.get('/api/v1/returns/')
        self.assertEqual(res.status_code, 200, res.content)
        body = res.json()
        self.assertIsInstance(body, list)
        self.assertEqual(len(body), 1)
        row = body[0]
        self.assertEqual(row['id'], str(rr.id))
        self.assertEqual(row['order_number'], self.order.order_number)
        self.assertIn('status_label', row)
        self.assertIn('status_message', row)
        self.assertIn('reason_detail', row)

    def test_list_returns_anonymous_401(self):
        res = self.client.get('/api/v1/returns/')
        self.assertEqual(res.status_code, 401)
