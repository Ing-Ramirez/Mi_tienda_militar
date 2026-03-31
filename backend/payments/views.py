from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .models import Payment
from orders.models import Order


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
            Payment.objects.filter(payment_id=intent['id']).update(status='succeeded')
            order_number = intent.get('metadata', {}).get('order_number')
            Order.objects.filter(order_number=order_number).update(
                payment_status='paid', status='confirmed',
            )
            # Encolar acumulación de puntos de fidelidad
            if order_number:
                try:
                    order_id = str(
                        Order.objects.only('id').get(order_number=order_number).pk
                    )
                    from loyalty.tasks import assign_loyalty_points
                    assign_loyalty_points.delay(order_id)
                except Order.DoesNotExist:
                    pass

        elif event['type'] == 'payment_intent.payment_failed':
            intent = event['data']['object']
            Payment.objects.filter(payment_id=intent['id']).update(status='failed')

        return Response({'status': 'ok'})


class PayPalCreateOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return Response({'detail': 'PayPal no configurado en este entorno.'}, status=501)


class PayPalCaptureView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return Response({'detail': 'PayPal no configurado en este entorno.'}, status=501)
