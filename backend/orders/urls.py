from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'cart', views.CartViewSet, basename='cart')
router.register(r'orders', views.OrderViewSet, basename='orders')

urlpatterns = [
    path('checkout/', views.CheckoutNekiView.as_view(), name='checkout'),
    path(
        'orders/<uuid:pk>/payment-proof/',
        views.OrderPaymentProofMediaView.as_view(),
        name='order_payment_proof_media',
    ),
    path('', include(router.urls)),
    path('coupons/validate/', views.CouponValidateView.as_view(), name='coupon-validate'),
]
