from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import logging
from .models import Payment
from orders.models import Order

logger = logging.getLogger(__name__)

class StripePaymentIntentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        order_number = request.data.get('order_number')
        try:
            order = Order.objects.get(order_number=order_number, user=request.user)
        except Order.DoesNotExist:
            return Response({'detail': 'Orden no encontrada.'}, status=404)

        intent = stripe.PaymentIntent.create(
            amount=int(order.total * 100),  # Stripe usa centavos
            currency='cop',
            metadata={'order_number': order.order_number},
            payment_method_options={
                'card': {
                    # 'automatic': Stripe activa 3DS según su modelo de riesgo.
                    # Reduce chargebacks transfiriendo responsabilidad al banco emisor.
                    'request_three_d_secure': 'automatic',
                }
            },
        )

        raw_safe = {
            'id': intent.get('id'),
            'status': intent.get('status'),
            'amount': intent.get('amount'),
            'currency': intent.get('currency'),
            'created': intent.get('created'),
        }
        Payment.objects.create(
            order=order,
            method='stripe',
            payment_id=intent['id'],
            amount=order.total,
            status='pending',
            raw_response=raw_safe,
        )

        return Response({'client_secret': intent['client_secret']})


@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        import stripe
        if not settings.STRIPE_WEBHOOK_SECRET and not settings.DEBUG:
            logger.error('STRIPE_WEBHOOK_SECRET no configurado en producción')
            return Response(status=503)
        stripe.api_key = settings.STRIPE_SECRET_KEY
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except (ValueError, stripe.error.SignatureVerificationError):
            return Response(status=400)

        if event['type'] == 'payment_intent.succeeded':
            intent = event['data']['object']
            payment_id = intent.get('id')
            amount_received = intent.get('amount_received') or intent.get('amount') or 0
            currency = (intent.get('currency') or '').lower()
            order_number = intent.get('metadata', {}).get('order_number')
            if not payment_id or not order_number:
                return Response(status=400)

            with transaction.atomic():
                try:
                    payment = (
                        Payment.objects
                        .select_for_update()
                        .select_related('order')
                        .get(payment_id=payment_id)
                    )
                except Payment.DoesNotExist:
                    return Response(status=404)

                order = payment.order
                expected_amount = int(order.total * 100)
                if (
                    order.order_number != order_number
                    or currency != 'cop'
                    or int(amount_received) != expected_amount
                ):
                    logger.warning(
                        'Webhook Stripe inconsistente payment_id=%s order=%s metadata_order=%s amount=%s expected=%s currency=%s',
                        payment_id, order.order_number, order_number, amount_received, expected_amount, currency,
                    )
                    return Response(status=400)

                if payment.status != 'succeeded':
                    payment.status = 'succeeded'
                    payment.save(update_fields=['status', 'updated_at'])

                should_enqueue_points = not order.loyalty_points_processed
                if order.payment_status != 'paid' or order.status == 'pending':
                    order.payment_status = 'paid'
                    order.status = 'confirmed'
                    order.save(update_fields=['payment_status', 'status', 'updated_at'])

            if should_enqueue_points:
                from loyalty.tasks import assign_loyalty_points
                assign_loyalty_points.delay(str(order.pk))

        elif event['type'] == 'payment_intent.payment_failed':
            intent = event['data']['object']
            payment_id = intent.get('id')
            if payment_id:
                Payment.objects.filter(
                    payment_id=payment_id,
                    status__in=['pending', 'processing'],
                ).update(status='failed')

        return Response({'status': 'ok'})


class PayPalCreateOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return Response({'detail': 'PayPal no configurado en este entorno.'}, status=501)


class PayPalCaptureView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return Response({'detail': 'PayPal no configurado en este entorno.'}, status=501)
