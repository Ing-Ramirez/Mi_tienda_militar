from django.urls import path
from . import views

urlpatterns = [
    path('balance/', views.LoyaltyBalanceView.as_view(), name='loyalty-balance'),
    path('transactions/', views.LoyaltyTransactionListView.as_view(), name='loyalty-transactions'),
    path('preview/', views.LoyaltyPreviewView.as_view(), name='loyalty-preview'),
]
