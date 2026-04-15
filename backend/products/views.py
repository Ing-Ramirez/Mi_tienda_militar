from django.db.models import Avg, Count, Q
from rest_framework import viewsets, generics, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from .models import Category, Product, ProductReview, ReviewEvidence, Favorito
from .serializers import (
    CategorySerializer, ProductListSerializer, ProductDetailSerializer,
    ReviewSerializer, ReviewReadSerializer, ReviewCreateSerializer,
    ReviewEvidenceSerializer,
)

MAX_HOME_PRODUCTS = 24


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
        """Devuelve array plano sin paginación (máx. uso en home/landing)."""
        qs = self.get_queryset().filter(is_featured=True)[:MAX_HOME_PRODUCTS]
        serializer = ProductListSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def new_arrivals(self, request):
        """Devuelve array plano sin paginación (máx. uso en home/landing)."""
        qs = self.get_queryset().filter(is_new=True)[:MAX_HOME_PRODUCTS]
        serializer = ProductListSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='reviews', url_name='reviews-list')
    def reviews(self, request, slug=None):
        """Lista de reseñas aprobadas del producto."""
        product = self.get_object()
        qs = (
            ProductReview.objects
            .filter(product=product, status='approved')
            .prefetch_related('evidence')
            .order_by('-created_at')
        )
        serializer = ReviewReadSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data)

    @action(
        detail=True, methods=['post'],
        permission_classes=[IsAuthenticated],
        parser_classes=[JSONParser, MultiPartParser, FormParser],
        url_path='reviews/create', url_name='reviews-create',
    )
    def create_review(self, request, slug=None):
        """Crear reseña (solo compradores verificados con pedido entregado)."""
        product = self.get_object()
        ser = ReviewCreateSerializer(
            data=request.data,
            context={'request': request, 'product': product},
        )
        ser.is_valid(raise_exception=True)
        review = ser.save(product=product, user=request.user)

        # Subir imágenes de evidencia opcionales (hasta 5)
        images = request.FILES.getlist('images')
        for img in images[:5]:
            ReviewEvidence.objects.create(review=review, image=img)

        return Response(
            ReviewReadSerializer(review, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated],
            url_path='eligible-reviews', url_name='eligible-reviews')
    def eligible_reviews(self, request):
        """
        Retorna lista de productos que el usuario puede calificar:
        pedidos entregados con productos aún no reseñados.
        """
        from orders.models import Order
        delivered_orders = Order.objects.filter(
            user=request.user, status='delivered'
        ).prefetch_related('items__product')

        already_reviewed_product_ids = set(
            str(pid) for pid in
            ProductReview.objects.filter(user=request.user)
            .values_list('product_id', flat=True)
        )

        eligible = []
        seen_product_order = set()
        for order in delivered_orders:
            for item in order.items.all():
                if not item.product:
                    continue
                key = (str(item.product_id), str(order.id))
                if key in seen_product_order:
                    continue
                seen_product_order.add(key)
                if str(item.product_id) in already_reviewed_product_ids:
                    continue
                eligible.append({
                    'order_id':     str(order.id),
                    'order_number': order.order_number,
                    'product_id':   str(item.product_id),
                    'product_name': item.product_name,
                    'product_slug': item.product.slug if item.product else None,
                })
        return Response(eligible)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def add_review(self, request, slug=None):
        """Endpoint legacy — redirige a create_review."""
        return self.create_review(request, slug=slug)


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
