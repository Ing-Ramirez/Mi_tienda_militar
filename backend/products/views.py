from django.db.models import Avg, Count, Q
from rest_framework import viewsets, generics, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from .models import Category, Product, ProductReview, Favorito
from .serializers import (
    CategorySerializer, ProductListSerializer, ProductDetailSerializer, ReviewSerializer
)


def _base_product_qs():
    """Queryset base con anotaciones de rating y conteo de reseñas."""
    return (
        Product.objects
        .filter(status='active')
        .select_related('category')
        .prefetch_related('variants', 'images')
        .annotate(
            avg_rating=Avg('reviews__rating', filter=Q(reviews__is_approved=True)),
            review_count_val=Count('reviews', filter=Q(reviews__is_approved=True)),
        )
    )


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = _base_product_qs()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['category', 'status', 'is_featured', 'is_new', 'personalization_type']
    search_fields = ['name', 'sku', 'description']
    ordering_fields = ['price', 'created_at', 'name']
    lookup_field = 'slug'

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ProductDetailSerializer
        return ProductListSerializer

    @action(detail=False, methods=['get'])
    def featured(self, request):
        qs = self.get_queryset().filter(is_featured=True)
        serializer = ProductListSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def new_arrivals(self, request):
        qs = self.get_queryset().filter(is_new=True)
        serializer = ProductListSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def add_review(self, request, slug=None):
        product = self.get_object()
        if ProductReview.objects.filter(product=product, user=request.user).exists():
            return Response(
                {'detail': 'Ya has dejado una reseña para este producto.'}, status=400
            )
        serializer = ReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(product=product, user=request.user)
        return Response(serializer.data, status=201)


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CategorySerializer
    lookup_field = 'slug'
    pagination_class = None  # devuelve array directo, sin paginación

    def get_queryset(self):
        # Categorías activas que tengan al menos un producto (cualquier estado)
        return (
            Category.objects
            .filter(is_active=True, products__isnull=False)
            .distinct()
            .order_by('order', 'name')
        )


class FavoritoListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ProductListSerializer

    def get_queryset(self):
        favorito_ids = Favorito.objects.filter(
            user=self.request.user
        ).values_list('product_id', flat=True)
        return _base_product_qs().filter(id__in=favorito_ids)


class FavoritoToggleView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, product_id):
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response({'detail': 'Producto no encontrado.'}, status=404)

        fav, created = Favorito.objects.get_or_create(user=request.user, product=product)
        if not created:
            fav.delete()
            return Response({'status': 'removed', 'message': 'Eliminado de favoritos.'})
        return Response({'status': 'added', 'message': 'Agregado a favoritos.'}, status=201)
