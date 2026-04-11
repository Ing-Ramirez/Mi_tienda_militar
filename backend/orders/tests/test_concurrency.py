"""
Tests de concurrencia — módulo Cart / Orders
============================================

Valida que los fixes de race conditions y overselling eliminan inconsistencias
bajo carga concurrente real (múltiples threads con transacciones separadas).

Se usa TransactionTestCase (no TestCase) porque los threads necesitan ver commits
de otros threads; TestCase envuelve todo en una transacción que los bloquearía.

Escenarios
----------
1. ADD_ITEM concurrente
   - N threads agregan qty al mismo CartItem simultáneamente.
   - Mecanismo bajo prueba: select_for_update() + F('quantity').
   - Invariante: cantidad_final == inicial + N×qty, exactamente 1 ítem.

2. Verificación de órdenes con stock limitado (anti-overselling)
   - 3 órdenes simultáneas para un producto con stock_by_size={'M': 2}.
   - Mecanismo bajo prueba: select_for_update() en Product dentro de
     _descontar_stock_orden + rollback del atomic() exterior si hay error.
   - Invariante: stock >= 0, verificadas <= stock_inicial, al menos 1 falla.

3. Rollback al fallar _descontar_stock_orden
   - Mock o stock real insuficiente provocan ValueError en el descuento.
   - Mecanismo bajo prueba: transaction.atomic() en el signal handler.
   - Invariante: orden queda PENDING, payment_status sin cambio, stock intacto.
"""
import threading
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.test import TransactionTestCase, override_settings

from orders.models import Cart, CartItem, ManualPaymentStatus, Order, OrderItem
from products.models import Category, Product

User = get_user_model()

# ── Fixtures mínimas ─────────────────────────────────────────────────────────

CELERY_ALWAYS_EAGER = {
    'CELERY_TASK_ALWAYS_EAGER': True,
    'CELERY_TASK_EAGER_PROPAGATES': False,
}


def _categoria():
    cat, _ = Category.objects.get_or_create(
        slug='test-uniformes',
        defaults={'name': 'Test Uniformes', 'is_active': True},
    )
    return cat


def _producto(
    sku='TEST-001',
    nombre='Uniforme de prueba',
    stock=10,
    requires_size=False,
    stock_by_size=None,
):
    """
    Crea un producto de prueba.

    Para productos CON talla (requires_size=True): pasar stock_by_size como dict.
    Product.save() recalculará stock y available_sizes automáticamente.
    """
    return Product.objects.create(
        name=nombre,
        sku=sku,
        description='Producto de prueba para tests de concurrencia.',
        price=Decimal('50000'),
        category=_categoria(),
        stock=stock,
        requires_size=requires_size,
        stock_by_size=stock_by_size or {},
        status='active',
    )


def _orden(usuario, producto, cantidad=1, talla='', estado_mp=ManualPaymentStatus.PENDING):
    """
    Crea directamente una Order + OrderItem en estado PENDING.
    No dispara despacho a proveedores (no es VERIFIED).
    """
    precio = producto.price
    orden = Order.objects.create(
        user=usuario,
        email=usuario.email,
        shipping_full_name='Usuario Prueba',
        shipping_phone='3001234567',
        shipping_country='Colombia',
        shipping_department='Bogotá D.C.',
        shipping_city='Bogotá',
        shipping_address_line1='Calle 1 # 2-3',
        subtotal=precio * cantidad,
        shipping_cost=Decimal('15000'),
        tax_amount=Decimal('0'),
        total=precio * cantidad + Decimal('15000'),
        status='pending',
        payment_status='pending',
        payment_method='neki',
        manual_payment_status=estado_mp,
    )
    OrderItem.objects.create(
        order=orden,
        product=producto,
        product_name=producto.name,
        product_sku=producto.sku,
        talla=talla,
        quantity=cantidad,
        unit_price=precio,
        line_total=precio * cantidad,
    )
    return orden


# ══════════════════════════════════════════════════════════════════════════════
# ESCENARIO 1 — ADD_ITEM concurrente
# ══════════════════════════════════════════════════════════════════════════════

class TestAddItemConcurrente(TransactionTestCase):
    """
    Valida que múltiples threads que incrementan la cantidad del mismo
    CartItem simultáneamente no pierden actualizaciones.

    Mecanismo: select_for_update() serializa el acceso a la fila;
    F('quantity') evalúa el incremento en la DB (no en Python), eliminando
    la ventana de race condition del patrón read-modify-write.
    """

    def setUp(self):
        self.usuario = User.objects.create_user(
            'cart_test', email='cart_test@franjapixelada.co', password='testpass123'
        )
        # Producto sin restricción de stock (requires_size=False, stock=0 → sin límite)
        self.producto = _producto(sku='CART-CONC-001', stock=0)
        self.cart = Cart.objects.create(user=self.usuario)
        # Pre-crear el ítem para que todos los threads entren por la rama de UPDATE
        self.item = CartItem.objects.create(
            cart=self.cart,
            product=self.producto,
            variant=None,
            talla='',
            bordado='',
            rh='',
            quantity=1,
            price_at_addition=self.producto.price,
        )

    def _incrementar(self, qty, barrier, errores):
        """
        Replica la lógica de CartViewSet.add_item para ítems sin personalización:
        select_for_update + F('quantity') dentro de un atomic().
        """
        try:
            barrier.wait()  # sincronizar arranque de todos los threads
            with transaction.atomic():
                try:
                    item = CartItem.objects.select_for_update().get(
                        cart=self.cart,
                        product=self.producto,
                        variant=None,
                        talla='',
                        bordado='',
                        rh='',
                    )
                    CartItem.objects.filter(pk=item.pk).update(
                        quantity=models.F('quantity') + qty
                    )
                except CartItem.DoesNotExist:
                    CartItem.objects.create(
                        cart=self.cart,
                        product=self.producto,
                        variant=None,
                        talla='',
                        bordado='',
                        rh='',
                        quantity=qty,
                        price_at_addition=self.producto.price,
                    )
        except Exception as exc:
            errores.append(exc)

    def test_cantidad_final_correcta(self):
        """
        PASS si: cantidad_final == cantidad_inicial + N_threads × qty_por_thread
        FAIL si: algún incremento se pierde (race condition en lectura concurrente)
        """
        N = 8
        QTY = 3
        CANTIDAD_INICIAL = 1
        errores = []
        barrier = threading.Barrier(N)

        threads = [
            threading.Thread(target=self._incrementar, args=(QTY, barrier, errores))
            for _ in range(N)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertFalse(
            errores,
            f'[ESCENARIO 1] Errores en threads: {errores}',
        )

        self.item.refresh_from_db()
        esperado = CANTIDAD_INICIAL + N * QTY
        self.assertEqual(
            self.item.quantity,
            esperado,
            f'[ESCENARIO 1] FAIL — Pérdida de incremento: '
            f'esperado={esperado}, obtenido={self.item.quantity}. '
            f'Race condition NO corregida.',
        )

    def test_sin_items_duplicados(self):
        """
        PASS si: exactamente 1 CartItem existe para (cart, producto, talla='')
        FAIL si: se crean múltiples filas (fallo de unicidad bajo concurrencia)
        """
        N = 6
        errores = []
        barrier = threading.Barrier(N)

        threads = [
            threading.Thread(target=self._incrementar, args=(1, barrier, errores))
            for _ in range(N)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        count = CartItem.objects.filter(
            cart=self.cart, product=self.producto
        ).count()
        self.assertEqual(
            count, 1,
            f'[ESCENARIO 1] FAIL — Se encontraron {count} ítems en lugar de 1. '
            f'Probable IntegrityError silenciado o lógica de deduplicación rota.',
        )


# ══════════════════════════════════════════════════════════════════════════════
# ESCENARIO 2 — Verificación concurrente con stock limitado (anti-overselling)
# ══════════════════════════════════════════════════════════════════════════════

@override_settings(**CELERY_ALWAYS_EAGER)
class TestVerificacionConcurrenteOrdenes(TransactionTestCase):
    """
    3 órdenes intentan verificarse simultáneamente para un producto con stock=2.
    Se usa requires_size=True porque con requires_size=False y stock=0 el sistema
    interpreta '0' como 'sin restricción' (comportamiento de diseño documentado).

    El mecanismo select_for_update() en _descontar_stock_orden garantiza que el
    descuento es atómico y serializado. La orden que llega cuando stock < qty
    debe obtener ValueError y su transacción se revierte completamente.
    """

    STOCK_INICIAL = 2
    TALLA = 'M'
    N_ORDENES = 3

    def setUp(self):
        self.producto = _producto(
            sku='STOCK-LIM-001',
            requires_size=True,
            stock_by_size={self.TALLA: self.STOCK_INICIAL},
        )
        self.usuarios = [
            User.objects.create_user(
                f'ord_user_{i}',
                email=f'ord{i}@franjapixelada.co',
                password='testpass123',
            )
            for i in range(self.N_ORDENES)
        ]
        self.ordenes = [
            _orden(u, self.producto, cantidad=1, talla=self.TALLA)
            for u in self.usuarios
        ]

    def _verificar(self, order_id, verificadas, fallidas, lock, barrier):
        """
        Simula la acción de admin de marcar una orden como VERIFIED.
        El signal _order_enqueue_dispatch_when_verified gestiona el descuento.
        """
        try:
            barrier.wait()
            with transaction.atomic():
                orden = Order.objects.select_for_update().get(pk=order_id)
                # Guardia: no re-procesar si ya fue verificada por otra transacción
                if orden.manual_payment_status == ManualPaymentStatus.VERIFIED:
                    return
                orden.manual_payment_status = ManualPaymentStatus.VERIFIED
                orden.save()
            with lock:
                verificadas.append(order_id)
        except Exception:
            with lock:
                fallidas.append(order_id)

    @patch('orders.tasks.send_order_to_provider.delay')
    @patch('loyalty.tasks.assign_loyalty_points.delay')
    def test_stock_nunca_negativo(self, _loyalty, _dispatch):
        """
        PASS si: stock_final >= 0 (overselling nunca ocurre)
        FAIL si: stock cae por debajo de 0 (fallo de serialización)
        """
        verificadas, fallidas = [], []
        lock = threading.Lock()
        barrier = threading.Barrier(self.N_ORDENES)

        threads = [
            threading.Thread(
                target=self._verificar,
                args=(str(o.pk), verificadas, fallidas, lock, barrier),
            )
            for o in self.ordenes
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.producto.refresh_from_db()
        self.assertGreaterEqual(
            self.producto.stock,
            0,
            f'[ESCENARIO 2] FAIL — Stock negativo: {self.producto.stock}. '
            f'Overselling detectado. verificadas={len(verificadas)}, fallidas={len(fallidas)}.',
        )

    @patch('orders.tasks.send_order_to_provider.delay')
    @patch('loyalty.tasks.assign_loyalty_points.delay')
    def test_no_mas_verificadas_que_stock(self, _loyalty, _dispatch):
        """
        PASS si: verificadas <= STOCK_INICIAL y fallidas >= 1
        FAIL si: más órdenes que stock son verificadas (overselling lógico)
        """
        verificadas, fallidas = [], []
        lock = threading.Lock()
        barrier = threading.Barrier(self.N_ORDENES)

        threads = [
            threading.Thread(
                target=self._verificar,
                args=(str(o.pk), verificadas, fallidas, lock, barrier),
            )
            for o in self.ordenes
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.producto.refresh_from_db()

        self.assertGreaterEqual(
            self.producto.stock,
            0,
            f'[ESCENARIO 2] FAIL — Stock negativo: {self.producto.stock}',
        )
        self.assertLessEqual(
            len(verificadas),
            self.STOCK_INICIAL,
            f'[ESCENARIO 2] FAIL — {len(verificadas)} órdenes verificadas con stock={self.STOCK_INICIAL}. '
            f'Overselling confirmado.',
        )
        self.assertGreaterEqual(
            len(fallidas),
            1,
            f'[ESCENARIO 2] FAIL — 0 órdenes fallidas; todas pasaron con stock={self.STOCK_INICIAL}. '
            f'La validación de stock no está funcionando.',
        )

    @patch('orders.tasks.send_order_to_provider.delay')
    @patch('loyalty.tasks.assign_loyalty_points.delay')
    def test_stock_descontado_exactamente(self, _loyalty, _dispatch):
        """
        PASS si: stock_final == STOCK_INICIAL - len(verificadas)
        FAIL si: el stock descontado no coincide con las verificaciones reales
        """
        verificadas, fallidas = [], []
        lock = threading.Lock()
        barrier = threading.Barrier(self.N_ORDENES)

        threads = [
            threading.Thread(
                target=self._verificar,
                args=(str(o.pk), verificadas, fallidas, lock, barrier),
            )
            for o in self.ordenes
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.producto.refresh_from_db()
        stock_esperado = self.STOCK_INICIAL - len(verificadas)
        self.assertEqual(
            self.producto.stock,
            stock_esperado,
            f'[ESCENARIO 2] FAIL — Stock inconsistente: '
            f'esperado={stock_esperado} (inicial={self.STOCK_INICIAL}, verificadas={len(verificadas)}), '
            f'real={self.producto.stock}. Probable descuento doble o parcial.',
        )


# ══════════════════════════════════════════════════════════════════════════════
# ESCENARIO 3 — Rollback completo al fallar _descontar_stock_orden
# ══════════════════════════════════════════════════════════════════════════════

@override_settings(**CELERY_ALWAYS_EAGER)
class TestRollbackDescuentoFallido(TransactionTestCase):
    """
    Cuando _descontar_stock_orden lanza ValueError (stock insuficiente real o
    error simulado), la transacción atómica del signal handler debe revertirse
    por completo:

    - La orden permanece en manual_payment_status=PENDING.
    - payment_status y status de la orden no cambian.
    - El stock del producto no se modifica.

    El signal re-lanza la excepción. Si la llamada a order.save() está envuelta
    en transaction.atomic() (como hace el admin), el rollback incluye también
    la escritura de VERIFIED, dejando la orden completamente sin cambios.
    """

    def setUp(self):
        self.usuario = User.objects.create_user(
            'rollback_user', email='rollback@franjapixelada.co', password='testpass123'
        )
        self.producto = _producto(sku='ROLL-001', stock=5)
        self.orden = _orden(self.usuario, self.producto, cantidad=1)

    # ── 3a. Mock: _descontar_stock_orden falla intencionalmente ──────────────

    @patch(
        'orders.signals._descontar_stock_orden',
        side_effect=ValueError('Error simulado de descuento'),
    )
    def test_orden_no_marcada_verificada_tras_rollback(self, _mock):
        """
        PASS si: orden.manual_payment_status permanece PENDING
        FAIL si: la orden queda VERIFIED a pesar del error (rollback incompleto)
        """
        with self.assertRaises(ValueError):
            with transaction.atomic():
                self.orden.manual_payment_status = ManualPaymentStatus.VERIFIED
                self.orden.save()

        self.orden.refresh_from_db()
        self.assertEqual(
            self.orden.manual_payment_status,
            ManualPaymentStatus.PENDING,
            '[ESCENARIO 3a] FAIL — La orden quedó VERIFIED a pesar del error. '
            'El rollback no revirtió la escritura del estado.',
        )

    @patch(
        'orders.signals._descontar_stock_orden',
        side_effect=ValueError('Error simulado de descuento'),
    )
    def test_payment_status_sin_cambio_tras_rollback(self, _mock):
        """
        PASS si: payment_status y status permanecen 'pending'
        FAIL si: cambiaron a 'paid'/'processing' (rollback parcial del signal)
        """
        status_antes = self.orden.status
        payment_antes = self.orden.payment_status

        try:
            with transaction.atomic():
                self.orden.manual_payment_status = ManualPaymentStatus.VERIFIED
                self.orden.save()
        except ValueError:
            pass

        self.orden.refresh_from_db()
        self.assertEqual(
            self.orden.status,
            status_antes,
            f'[ESCENARIO 3a] FAIL — order.status cambió: {status_antes} → {self.orden.status}',
        )
        self.assertEqual(
            self.orden.payment_status,
            payment_antes,
            f'[ESCENARIO 3a] FAIL — payment_status cambió: {payment_antes} → {self.orden.payment_status}',
        )

    @patch(
        'orders.signals._descontar_stock_orden',
        side_effect=ValueError('Error simulado de descuento'),
    )
    def test_stock_intacto_tras_rollback_con_mock(self, _mock):
        """
        PASS si: stock no cambia cuando _descontar_stock_orden está mockeado
        FAIL si: el stock cambió (lógica de descuento se ejecutó de todos modos)
        """
        stock_antes = self.producto.stock

        try:
            with transaction.atomic():
                self.orden.manual_payment_status = ManualPaymentStatus.VERIFIED
                self.orden.save()
        except ValueError:
            pass

        self.producto.refresh_from_db()
        self.assertEqual(
            self.producto.stock,
            stock_antes,
            f'[ESCENARIO 3a] FAIL — Stock cambió de {stock_antes} a {self.producto.stock} '
            f'a pesar de que _descontar_stock_orden estaba mockeado.',
        )

    # ── 3b. Real: stock insuficiente provoca ValueError sin mock ─────────────

    @patch('orders.tasks.send_order_to_provider.delay')
    @patch('loyalty.tasks.assign_loyalty_points.delay')
    def test_rollback_real_stock_insuficiente(self, _loyalty, _dispatch):
        """
        Sin mock: la orden solicita más unidades de las disponibles.
        _descontar_stock_orden detecta el faltante y lanza ValueError real.

        PASS si: orden permanece PENDING, stock sin cambio
        FAIL si: la orden pasa a VERIFIED o el stock queda inconsistente
        """
        stock_antes = self.producto.stock
        # Aumentar la cantidad del ítem a más del stock disponible
        self.orden.items.update(quantity=stock_antes + 10)

        try:
            with transaction.atomic():
                self.orden.manual_payment_status = ManualPaymentStatus.VERIFIED
                self.orden.save()
        except (ValueError, Exception):
            pass  # esperado

        self.orden.refresh_from_db()
        self.assertEqual(
            self.orden.manual_payment_status,
            ManualPaymentStatus.PENDING,
            '[ESCENARIO 3b] FAIL — La orden quedó VERIFIED con stock insuficiente. '
            'El rollback real no funcionó.',
        )

        self.producto.refresh_from_db()
        self.assertEqual(
            self.producto.stock,
            stock_antes,
            f'[ESCENARIO 3b] FAIL — Stock cambió de {stock_antes} a {self.producto.stock} '
            f'a pesar del rollback.',
        )
        self.assertGreaterEqual(
            self.producto.stock,
            0,
            f'[ESCENARIO 3b] FAIL — Stock negativo: {self.producto.stock}',
        )

    @patch('orders.tasks.send_order_to_provider.delay')
    @patch('loyalty.tasks.assign_loyalty_points.delay')
    def test_rollback_real_producto_con_talla_insuficiente(self, _loyalty, _dispatch):
        """
        Mismo rollback real pero para producto requires_size=True.
        Valida que stock_by_size tampoco se modifica parcialmente.
        """
        producto_talla = _producto(
            sku='ROLL-TALLA-001',
            requires_size=True,
            stock_by_size={'M': 2},
        )
        orden_talla = _orden(
            self.usuario, producto_talla, cantidad=99, talla='M'
        )

        sbs_antes = dict(producto_talla.stock_by_size)
        stock_antes = producto_talla.stock

        try:
            with transaction.atomic():
                orden_talla.manual_payment_status = ManualPaymentStatus.VERIFIED
                orden_talla.save()
        except (ValueError, Exception):
            pass

        orden_talla.refresh_from_db()
        self.assertEqual(
            orden_talla.manual_payment_status,
            ManualPaymentStatus.PENDING,
            '[ESCENARIO 3b talla] FAIL — La orden quedó VERIFIED con stock_by_size insuficiente.',
        )

        producto_talla.refresh_from_db()
        self.assertEqual(
            producto_talla.stock,
            stock_antes,
            f'[ESCENARIO 3b talla] FAIL — stock cambió: {stock_antes} → {producto_talla.stock}',
        )
        self.assertEqual(
            producto_talla.stock_by_size,
            sbs_antes,
            f'[ESCENARIO 3b talla] FAIL — stock_by_size modificado parcialmente: '
            f'antes={sbs_antes}, después={producto_talla.stock_by_size}',
        )
