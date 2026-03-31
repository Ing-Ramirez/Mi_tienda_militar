"""
Proveedores — Vistas

WebhookProveedorView    → endpoint público para recibir webhooks (valida firma HMAC)
EstadoProveedoresView   → endpoint interno (solo admin) para monitorear proveedores
LogsProveedorView       → endpoint interno para consultar logs de un proveedor
"""
import hmac
import hashlib
import logging

from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser

from .models import Supplier, SupplierLog, EventType, LinkedProduct, SupplierVariant
from .serializers import (
    ProveedorEstadoSerializer, LogProveedorSerializer,
    VarianteProveedorCatalogoSerializer, ProductoVinculadoSerializer,
)
from .tasks import procesar_webhook
from .services.stock_dinamico import ServicioStockDinamico
from .throttles import WebhookAnonThrottle

logger = logging.getLogger(__name__)


class WebhookProveedorView(APIView):
    """
    Endpoint público para recibir webhooks de proveedores.

    URL: POST /api/v1/proveedores/webhooks/<proveedor_slug>/

    Flujo:
      1. Identificar el proveedor por slug.
      2. Validar la firma HMAC (si el proveedor tiene webhook_secret configurado).
      3. Rechazar con 401 si la firma es inválida — registrar el intento en SupplierLog.
      4. Registrar el evento en SupplierLog.
      5. Encolar el procesamiento asíncrono con Celery (no bloquea la respuesta).
      6. Responder 200 inmediatamente.

    Seguridad:
      - Sin autenticación JWT (el proveedor externo no tiene tokens internos).
      - Validación por firma HMAC-SHA256 (cabecera X-Webhook-Signature o X-Hub-Signature-256).
      - Límite de tasa por IP para contener abuso y picos anómalos.
    """
    authentication_classes = []
    permission_classes     = []
    throttle_classes       = [WebhookAnonThrottle]

    def post(self, request, proveedor_slug):
        # 1. Buscar proveedor activo o en prueba
        proveedor = get_object_or_404(
            Supplier,
            slug   = proveedor_slug,
            status__in = ['activo', 'prueba'],
        )

        # 2. Validar firma HMAC
        if not self._validar_firma(request, proveedor):
            SupplierLog.objects.create(
                supplier    = proveedor,
                event_type  = EventType.WEBHOOK_ENTRANTE,
                payload     = {
                    'ip':      request.META.get('REMOTE_ADDR', ''),
                    'headers': {
                        k: v for k, v in request.headers.items()
                        if k.lower().startswith('x-')
                    },
                },
                status  = 'rechazado',
                message = 'Firma HMAC inválida — webhook rechazado.',
            )
            return Response({'error': 'Firma inválida'}, status=401)

        # 3. Extraer tipo de evento
        datos       = request.data
        tipo_evento = (
            datos.get('event')
            or datos.get('type')
            or request.headers.get('X-Event-Type', 'unknown')
        )

        # 4. Registrar log inmediatamente
        SupplierLog.objects.create(
            supplier    = proveedor,
            event_type  = EventType.WEBHOOK_ENTRANTE,
            payload     = datos,
            status      = 'ok',
            message     = f'Evento recibido: {tipo_evento}',
        )

        # 5. Encolar procesamiento asíncrono
        procesar_webhook.delay(str(proveedor.id), tipo_evento, datos)

        # 6. Responder 200 inmediatamente (el proveedor no espera procesamiento)
        return Response({'status': 'recibido'}, status=200)

    def _validar_firma(self, request, proveedor) -> bool:
        """
        Valida la firma HMAC-SHA256 del payload.
        Sin `webhook_secret`, solo se acepta el cuerpo si WEBHOOK_ALLOW_UNSIGNED=True
        (.env de desarrollo explícito — nunca en producción).
        """
        if not proveedor.webhook_secret:
            return bool(getattr(settings, 'WEBHOOK_ALLOW_UNSIGNED', False))

        # Soporta tanto X-Webhook-Signature como X-Hub-Signature-256 (formato GitHub)
        firma_recibida = (
            request.headers.get('X-Webhook-Signature', '')
            or request.headers.get('X-Hub-Signature-256', '')
        )
        # Remover prefijo "sha256=" si viene en formato GitHub
        firma_recibida = firma_recibida.removeprefix('sha256=')

        if not firma_recibida:
            return False

        firma_esperada = hmac.new(
            proveedor.webhook_secret.encode(),
            request.body,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(firma_recibida, firma_esperada)


class EstadoProveedoresView(APIView):
    """
    Lista todos los proveedores con su estado de sincronización.
    Solo accesible para administradores del sistema.

    URL: GET /api/v1/proveedores/estado/
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        proveedores = Supplier.objects.all()
        return Response(ProveedorEstadoSerializer(proveedores, many=True).data)


class LogsProveedorView(APIView):
    """
    Devuelve los últimos 100 logs de un proveedor específico.
    URL: GET /api/v1/proveedores/<proveedor_slug>/logs/
    """
    permission_classes = [IsAdminUser]

    def get(self, request, proveedor_slug):
        proveedor = get_object_or_404(Supplier, slug=proveedor_slug)
        logs = SupplierLog.objects.filter(supplier=proveedor)[:100]
        return Response(LogProveedorSerializer(logs, many=True).data)


class CatalogoProveedorView(APIView):
    """
    Lista el catálogo de variantes sincronizadas de un proveedor.
    Permite al operador ver qué productos están disponibles para vincular.

    URL: GET /api/v1/proveedores/<proveedor_slug>/catalogo/
    Filtros: ?estado=activo|agotado   ?sin_vincular=true
    """
    permission_classes = [IsAdminUser]

    def get(self, request, proveedor_slug):
        proveedor = get_object_or_404(Supplier, slug=proveedor_slug)

        qs = SupplierVariant.objects.filter(
            supplier_product__supplier=proveedor,
        ).select_related('supplier_product').order_by('supplier_product__name', 'sku')

        estado = request.query_params.get('estado')
        if estado:
            qs = qs.filter(status=estado)

        # Solo variantes sin vínculo activo
        if request.query_params.get('sin_vincular') == 'true':
            qs = qs.exclude(vinculos__is_active=True)

        return Response(VarianteProveedorCatalogoSerializer(qs, many=True).data)


class ProductoVinculadoView(APIView):
    """
    Lista y crea vínculos entre variantes del proveedor y productos del catálogo.

    GET  /api/v1/proveedores/vinculados/         → lista todos los vínculos
    POST /api/v1/proveedores/vinculados/         → crea un nuevo vínculo
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        qs = LinkedProduct.objects.select_related(
            'supplier_variant__supplier_product__supplier', 'local_product',
        ).all()
        return Response(ProductoVinculadoSerializer(qs, many=True).data)

    def post(self, request):
        serializer = ProductoVinculadoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vinculo = serializer.save()

        # Recalcular inmediatamente al crear el vínculo
        ServicioStockDinamico().recalcular(vinculo)

        return Response(ProductoVinculadoSerializer(vinculo).data, status=201)


class ProductoVinculadoDetalleView(APIView):
    """
    Detalle, edición y recálculo de un vínculo específico.

    GET    /api/v1/proveedores/vinculados/<id>/            → detalle
    PATCH  /api/v1/proveedores/vinculados/<id>/            → editar max_stock, is_active, etc.
    POST   /api/v1/proveedores/vinculados/<id>/recalcular/ → forzar recálculo ahora
    DELETE /api/v1/proveedores/vinculados/<id>/            → eliminar vínculo
    """
    permission_classes = [IsAdminUser]

    def _get_vinculo(self, pk):
        return get_object_or_404(
            LinkedProduct.objects.select_related(
                'supplier_variant__supplier_product__supplier', 'local_product',
            ),
            id=pk,
        )

    def get(self, request, pk):
        return Response(ProductoVinculadoSerializer(self._get_vinculo(pk)).data)

    def patch(self, request, pk):
        vinculo = self._get_vinculo(pk)
        serializer = ProductoVinculadoSerializer(vinculo, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        vinculo = serializer.save()
        ServicioStockDinamico().recalcular(vinculo)
        return Response(ProductoVinculadoSerializer(vinculo).data)

    def delete(self, request, pk):
        self._get_vinculo(pk).delete()
        return Response(status=204)


class RecalcularVinculoView(APIView):
    """Fuerza el recálculo inmediato de un vínculo. POST /api/v1/proveedores/vinculados/<id>/recalcular/"""
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        vinculo = get_object_or_404(
            LinkedProduct.objects.select_related('supplier_variant', 'local_product'),
            id=pk,
        )
        ServicioStockDinamico().recalcular(vinculo)
        return Response({
            'stock_proveedor': vinculo.stock_proveedor,
            'max_stock':       vinculo.max_stock,
            'stock_visible':   vinculo.stock_visible,
            'calculated_stock': vinculo.calculated_stock,
            'last_recalculated_at': vinculo.last_recalculated_at,
        })
