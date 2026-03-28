from django.urls import path
from . import views

urlpatterns = [
    path('stripe/create-intent/', views.StripePaymentIntentView.as_view(), name='stripe-intent'),
    path('stripe/webhook/', views.StripeWebhookView.as_view(), name='stripe-webhook'),
    path('paypal/create-order/', views.PayPalCreateOrderView.as_view(), name='paypal-create'),
    path('paypal/capture/', views.PayPalCaptureView.as_view(), name='paypal-capture'),
]
