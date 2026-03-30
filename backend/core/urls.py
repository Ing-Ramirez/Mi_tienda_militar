from django.urls import path
from .views import exchange_rate_live

urlpatterns = [
    path('exchange-rate/live/', exchange_rate_live, name='exchange_rate_live'),
]
