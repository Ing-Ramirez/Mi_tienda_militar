"""
Franja Pixelada — Views de Devoluciones

Endpoints:
  GET    /api/v1/returns/                → lista del usuario autenticado
  POST   /api/v1/returns/                → crear solicitud
  GET    /api/v1/returns/{id}/           → detalle
  POST   /api/v1/returns/{id}/evidence/  → subir imagen
  DELETE /api/v1/returns/{id}/evidence/{eid}/ → eliminar imagen (solo estado requested)
  POST   /api/v1/returns/{id}/transition/ → cambiar estado (admin)
  GET    /api/v1/returns/eligibility/{order_id}/ → verificar si orden puede iniciar devolución
"""
import logging
from datetime import timedelta

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ReturnRequest, ReturnEvidence, VALID_TRANSITIONS
from products.validators import validate_image_file
from .serializers import (
    ReturnRequestListSerializer,
    ReturnRequestDetailSerializer,
    ReturnCreateSerializer,
    ReturnEvidenceSerializer,
)

logger = logging.getLogger(__name__)


class ReturnListCreateView(APIView):
    """GET → lista del usuario | POST → crear solicitud."""
    permission_classes = [IsAuthenticated]
    parser_classes     = [JSONParser, MultiPartParser, FormParser]

    def get(self, request):
        qs = (
            ReturnRequest.objects
            .filter(user=request.user)
            .select_related('order')
            .prefetch_related('items', 'evidence', 'audit_log')
            .order_by('-requested_at')
        )
        ser = ReturnRequestListSerializer(qs, many=True, context={'request': request})
        return Response(ser.data)

    def post(self, request):
        ser = ReturnCreateSerializer(data=request.data, context={'request': request})
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        return_request = ser.save()
        return Response(
            ReturnRequestDetailSerializer(return_request, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )


class ReturnDetailView(APIView):
    """GET → detalle de la solicitud (cliente ve la suya; admin ve cualquiera)."""
    permission_classes = [IsAuthenticated]

    def _get_object(self, request, pk):
        if request.user.is_staff or request.user.is_superuser:
            return get_object_or_404(ReturnRequest, pk=pk)
        return get_object_or_404(ReturnRequest, pk=pk, user=request.user)

    def get(self, request, pk):
        obj = self._get_object(request, pk)
        return Response(
            ReturnRequestDetailSerializer(obj, context={'request': request}).data
        )


class ReturnEvidenceView(APIView):
    """POST → subir imagen | DELETE → eliminar imagen."""
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser]

    def post(self, request, pk):
        return_request = get_object_or_404(ReturnRequest, pk=pk, user=request.user)
        if return_request.status not in ('requested', 'reviewing'):
            return Response(
                {'detail': 'No se pueden agregar evidencias en este estado.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if return_request.evidence.count() >= 8:
            return Response(
                {'detail': 'Máximo 8 imágenes de evidencia por solicitud.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        image = request.FILES.get('image')
        if not image:
            return Response({'detail': 'Se requiere una imagen.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            validate_image_file(image)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        evidence = ReturnEvidence.objects.create(
            return_request=return_request,
            image=image,
            caption=request.data.get('caption', ''),
        )
        return Response(
            ReturnEvidenceSerializer(evidence, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )

    def delete(self, request, pk, eid):
        return_request = get_object_or_404(ReturnRequest, pk=pk, user=request.user)
        if return_request.status != 'requested':
            return Response(
                {'detail': 'Solo se pueden eliminar evidencias en estado Solicitada.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        evidence = get_object_or_404(ReturnEvidence, pk=eid, return_request=return_request)
        evidence.image.delete(save=False)
        evidence.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReturnTransitionView(APIView):
    """POST → cambiar estado (solo admin)."""
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        return_request = get_object_or_404(ReturnRequest, pk=pk)
        new_status     = request.data.get('status', '').strip()
        note           = request.data.get('note', '').strip()

        if new_status not in dict(VALID_TRANSITIONS):
            return Response({'detail': 'Estado inválido.'}, status=status.HTTP_400_BAD_REQUEST)

        if not return_request.can_transition_to(new_status):
            return Response(
                {'detail': f'No se puede pasar de "{return_request.status}" a "{new_status}".'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Datos extra opcionales para el reembolso
        if new_status == 'validated':
            refund_amount = request.data.get('refund_amount')
            refund_method = request.data.get('refund_method', '').strip()
            if refund_amount is not None:
                return_request.refund_amount = refund_amount
            if refund_method:
                return_request.refund_method = refund_method
            return_request.admin_notes = request.data.get('admin_notes', return_request.admin_notes)
            if not return_request.estimated_refund_at:
                eta_days = int(request.data.get('refund_eta_days', 7) or 7)
                return_request.estimated_refund_at = timezone.now() + timedelta(days=max(0, eta_days))
            return_request.save(update_fields=['refund_amount', 'refund_method', 'admin_notes', 'estimated_refund_at', 'updated_at'])

        if new_status in ('rejected_subsanable', 'rejected_definitive'):
            reason = request.data.get('rejection_reason', '').strip()
            if len(reason) < 3:
                return Response(
                    {
                        'detail': 'El motivo de rechazo (visible al cliente) es obligatorio — '
                        'ej.: falta de empaque, fuera de plazo, etc.',
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return_request.rejection_reason = reason
            return_request.rejected_at = timezone.now()
            return_request.admin_notes = request.data.get('admin_notes', return_request.admin_notes)
            return_request.refund_status = 'denied'
            return_request.save(update_fields=[
                'rejection_reason', 'rejected_at', 'admin_notes', 'refund_status', 'updated_at',
            ])

        try:
            return_request.transition(new_status, changed_by=request.user, note=note)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            ReturnRequestDetailSerializer(return_request, context={'request': request}).data
        )


class ReturnEligibilityView(APIView):
    """GET → verifica si una orden puede iniciar devolución."""
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        from django.conf import settings
        from orders.models import Order
        try:
            order = Order.objects.get(pk=order_id, user=request.user)
        except Order.DoesNotExist:
            return Response({'eligible': False, 'reason': 'Orden no encontrada.'})
        ok, msg = ReturnRequest.can_create_for_order(order)
        max_a = int(getattr(settings, 'RETURN_MAX_ATTEMPTS_PER_ORDER', 3))
        used = ReturnRequest.objects.filter(order=order).count()
        return Response({
            'eligible': ok,
            'reason': msg,
            'max_attempts': max_a,
            'attempts_used': used,
        })


class AdminReturnListView(APIView):
    """GET → todos las devoluciones (solo admin), con filtro por estado."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        qs = (
            ReturnRequest.objects
            .select_related('user', 'order')
            .prefetch_related('items', 'evidence')
            .order_by('-requested_at')
        )
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        search = request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(order__order_number__icontains=search) | qs.filter(user__email__icontains=search)
        return Response(ReturnRequestListSerializer(qs, many=True).data)


class ReturnPolicyView(APIView):
    """GET → políticas de devolución para UI (público: footer e información; el flujo de solicitud sigue exigiendo cuenta)."""
    permission_classes = [AllowAny]

    def get(self, request):
        from django.conf import settings

        from .models import RETURN_WINDOW_DAYS_NEW, RETURN_WINDOW_DAYS_USED, RETURN_SHIPMENT_WINDOW_DAYS
        from .policy_document import build_return_policy_document

        excluded = list(getattr(settings, 'RETURN_EXCLUDED_CATEGORY_SLUGS', []))
        digital_ex = bool(getattr(settings, 'RETURN_EXCLUDE_DIGITAL_PRODUCTS', True))
        sku_px = list(getattr(settings, 'RETURN_SPECIAL_SKU_PREFIXES', ['DIGI-', 'SPC-']))
        steps = [
            'Solicita la devolución desde Cuenta → Mis pedidos → detalle del pedido entregado.',
            'Lee y acepta las políticas en el paso intermedio obligatorio.',
            'Nuestro equipo revisa la solicitud y la evidencia enviada.',
            'Si se aprueba, envía el producto dentro del plazo indicado.',
            'Validamos el estado recibido y procesamos el reembolso por el canal correspondiente.',
        ]
        document = build_return_policy_document(
            window_days_new=RETURN_WINDOW_DAYS_NEW,
            window_days_used=RETURN_WINDOW_DAYS_USED,
            shipment_window_days=RETURN_SHIPMENT_WINDOW_DAYS,
            excluded_category_slugs=excluded,
            digital_exclusion_enabled=digital_ex,
            special_sku_prefixes=sku_px,
        )
        resp = Response({
            'window_days_new': RETURN_WINDOW_DAYS_NEW,
            'window_days_used': RETURN_WINDOW_DAYS_USED,
            'shipment_window_days': RETURN_SHIPMENT_WINDOW_DAYS,
            'excluded_category_slugs': excluded,
            'digital_exclusion_enabled': digital_ex,
            'special_sku_prefixes': sku_px,
            'steps': steps,
            'document': document,
        })
        resp['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        resp['Pragma'] = 'no-cache'
        return resp
