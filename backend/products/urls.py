from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'categories', views.CategoryViewSet, basename='category')
router.register(r'', views.ProductViewSet)

urlpatterns = [
    path('favoritos/', views.FavoritoListView.as_view(), name='favoritos'),
    path('favoritos/<uuid:product_id>/', views.FavoritoToggleView.as_view(), name='favorito-toggle'),
    path('', include(router.urls)),
]
