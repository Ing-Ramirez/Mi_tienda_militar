"""
Franja Pixelada — Vistas de Fidelidad

Ninguna lógica de negocio aquí: solo deserialización, delegación a services
y serialización de la respuesta.
"""
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .serializers import (
    LoyaltyAccountSerializer,
    PointTransactionSerializer,
    PointsPreviewSerializer,
)


class LoyaltyBalanceView(APIView):
    """
    GET /api/v1/loyalty/balance/
    Devuelve el saldo de puntos del usuario autenticado junto con
    la configuración de conversión (valor del punto, ratio de acumulación).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        account = services.get_or_create_account(request.user)
        return Response(LoyaltyAccountSerializer(account).data)


class LoyaltyTransactionListView(ListAPIView):
    """
    GET /api/v1/loyalty/transactions/
    Historial paginado de transacciones de puntos del usuario autenticado.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = PointTransactionSerializer

    def get_queryset(self):
        account = services.get_or_create_account(self.request.user)
        return account.transactions.select_related('order').order_by('-created_at')


class LoyaltyPreviewView(APIView):
    """
    POST /api/v1/loyalty/preview/
    Calcula el descuento que se aplicaría al usar N puntos en una orden de total X.
    No persiste ningún cambio.

    Body: { points_to_use: int, order_total: decimal }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = PointsPreviewSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        result = services.preview_redemption(
            user=request.user,
            points_to_use=ser.validated_data['points_to_use'],
            order_total=ser.validated_data['order_total'],
        )
        return Response(result)
