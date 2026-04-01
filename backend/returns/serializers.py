"""
Franja Pixelada — Serializers de Devoluciones
"""
from django.utils import timezone
from rest_framework import serializers

from orders.models import Order, OrderItem
from .models import (
    ReturnRequest, ReturnItem, ReturnEvidence, ReturnAuditLog,
    RETURN_WINDOW_DAYS_NEW,
    RETURN_WINDOW_DAYS_USED,
)


class ReturnEvidenceSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model  = ReturnEvidence
        fields = ['id', 'image_url', 'caption', 'uploaded_at']

    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return None


class ReturnAuditLogSerializer(serializers.ModelSerializer):
    changed_by_email = serializers.SerializerMethodField()
    from_status_label = serializers.SerializerMethodField()
    to_status_label   = serializers.SerializerMethodField()

    class Meta:
        model  = ReturnAuditLog
        fields = ['id', 'from_status', 'from_status_label',
                  'to_status', 'to_status_label',
                  'changed_by_email', 'note', 'created_at']

    def get_changed_by_email(self, obj):
        return obj.changed_by.email if obj.changed_by else 'Sistema'

    def _label(self, status):
        from .models import STATUS_CHOICES
        return dict(STATUS_CHOICES).get(status, status)

    def get_from_status_label(self, obj):
        return self._label(obj.from_status)

    def get_to_status_label(self, obj):
        return self._label(obj.to_status)


class ReturnItemSerializer(serializers.ModelSerializer):
    product_name    = serializers.CharField(source='order_item.product_name', read_only=True)
    product_sku     = serializers.CharField(source='order_item.product_sku',  read_only=True)
    unit_price      = serializers.DecimalField(
        source='order_item.unit_price', max_digits=12, decimal_places=2, read_only=True
    )
    condition_label = serializers.CharField(source='get_condition_display', read_only=True)

    class Meta:
        model  = ReturnItem
        fields = ['id', 'order_item', 'product_name', 'product_sku',
                  'unit_price', 'quantity', 'condition', 'condition_label',
                  'has_original_packaging']


class ReturnRequestListSerializer(serializers.ModelSerializer):
    """Serializer compacto para listados."""
    status_label        = serializers.SerializerMethodField()
    reason_label        = serializers.SerializerMethodField()
    refund_status_label = serializers.SerializerMethodField()
    order_number        = serializers.CharField(source='order.order_number',        read_only=True)
    items_count         = serializers.SerializerMethodField()
    return_code         = serializers.CharField(read_only=True)
    order_id            = serializers.UUIDField(source='order_id', read_only=True)
    attempt_number      = serializers.IntegerField(read_only=True)
    parent_return_id    = serializers.UUIDField(source='parent_return_id', read_only=True, allow_null=True)
    rejection_reason    = serializers.CharField(read_only=True)
    rejected_at         = serializers.DateTimeField(read_only=True)
    can_retry           = serializers.SerializerMethodField()
    customer_rejection_hint = serializers.SerializerMethodField()
    ui_rejection_tone   = serializers.SerializerMethodField()

    class Meta:
        model  = ReturnRequest
        fields = [
            'id', 'return_code', 'order_id', 'order_number', 'attempt_number',
            'parent_return_id',
            'reason', 'reason_label',
            'status', 'status_label', 'refund_status', 'refund_status_label',
            'refund_amount', 'items_count',
            'rejection_reason', 'rejected_at',
            'can_retry', 'customer_rejection_hint', 'ui_rejection_tone',
            'requested_at', 'resolved_at',
        ]

    def get_items_count(self, obj):
        return obj.items.count()

    def get_status_label(self, obj):
        return obj.get_status_display()

    def get_reason_label(self, obj):
        return obj.get_reason_display()

    def get_refund_status_label(self, obj):
        return obj.get_refund_status_display()

    def get_can_retry(self, obj):
        return obj.status == 'rejected_subsanable'

    def get_customer_rejection_hint(self, obj):
        if obj.status == 'rejected_subsanable':
            return 'Puedes corregir lo indicado y volver a intentar la devolución.'
        if obj.status == 'rejected_definitive':
            return 'No cumple condiciones de devolución. No es posible un nuevo intento.'
        return ''

    def get_ui_rejection_tone(self, obj):
        if obj.status == 'rejected_subsanable':
            return 'subsanable'
        if obj.status == 'rejected_definitive':
            return 'definitive'
        return 'neutral'


class ReturnRequestDetailSerializer(serializers.ModelSerializer):
    """Serializer completo con ítems, evidencias y auditoría."""
    status_label        = serializers.SerializerMethodField()
    reason_label        = serializers.SerializerMethodField()
    refund_status_label = serializers.SerializerMethodField()
    refund_method_label = serializers.SerializerMethodField()
    order_number        = serializers.CharField(source='order.order_number',        read_only=True)
    items               = ReturnItemSerializer(many=True, read_only=True)
    evidence            = ReturnEvidenceSerializer(many=True, read_only=True)
    audit_log           = ReturnAuditLogSerializer(many=True, read_only=True)
    next_transitions    = serializers.SerializerMethodField()

    class Meta:
        model  = ReturnRequest
        fields = ['id', 'order', 'order_number', 'reason', 'reason_label',
                  'reason_detail', 'status', 'status_label',
                  'customer_notes', 'admin_notes',
                  'rejection_reason', 'rejected_at',
                  'attempt_number', 'parent_return_id',
                  'refund_method', 'refund_method_label',
                  'refund_status', 'refund_status_label',
                  'refund_amount', 'refund_at', 'estimated_refund_at',
                  'return_code', 'shipping_deadline_at',
                  'items', 'evidence', 'audit_log',
                  'next_transitions', 'requested_at', 'resolved_at', 'updated_at']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if request and not (
            getattr(request.user, 'is_staff', False) or getattr(request.user, 'is_superuser', False)
        ):
            data.pop('admin_notes', None)
        return data

    def get_status_label(self, obj):
        return obj.get_status_display()

    def get_reason_label(self, obj):
        return obj.get_reason_display()

    def get_refund_status_label(self, obj):
        return obj.get_refund_status_display()

    def get_refund_method_label(self, obj):
        return obj.get_refund_method_display() if obj.refund_method else ''

    def get_next_transitions(self, obj):
        from .models import VALID_TRANSITIONS, STATUS_CHOICES
        labels = dict(STATUS_CHOICES)
        return [
            {'value': s, 'label': labels.get(s, s)}
            for s in VALID_TRANSITIONS.get(obj.status, [])
        ]


class ReturnCreateSerializer(serializers.Serializer):
    """Valida y crea una solicitud de devolución."""
    parent_return_id = serializers.UUIDField(required=False, allow_null=True)
    order_id       = serializers.UUIDField()
    reason         = serializers.ChoiceField(choices=[r[0] for r in ReturnRequest._meta.get_field('reason').choices])
    reason_detail  = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    customer_notes = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    refund_method  = serializers.ChoiceField(
        choices=[r[0] for r in ReturnRequest._meta.get_field('refund_method').choices],
        required=False, allow_blank=True
    )
    items = serializers.ListField(
        child=serializers.DictField(), min_length=1,
        help_text='Lista de {order_item_id, quantity, condition, has_original_packaging}'
    )

    def validate_parent_return_id(self, value):
        if not value:
            return value
        user = self.context['request'].user
        try:
            pr = ReturnRequest.objects.get(pk=value, user=user)
        except ReturnRequest.DoesNotExist:
            raise serializers.ValidationError('Devolución no encontrada.')
        self._parent_return = pr
        return value

    def validate_order_id(self, value):
        user = self.context['request'].user
        try:
            order = Order.objects.get(pk=value, user=user)
        except Order.DoesNotExist:
            raise serializers.ValidationError('Orden no encontrada.')
        parent = getattr(self, '_parent_return', None)
        if parent is not None and str(parent.order_id) != str(order.id):
            raise serializers.ValidationError('El reintento debe usar el mismo pedido que la devolución anterior.')
        ok, msg = ReturnRequest.can_create_for_order(order, parent_return=parent)
        if not ok:
            raise serializers.ValidationError(msg)
        self._order = order
        return value

    def validate(self, attrs):
        if attrs.get('reason') == 'other' and not attrs.get('reason_detail', '').strip():
            raise serializers.ValidationError({'reason_detail': 'Debes describir el motivo cuando seleccionas "Otro".'})
        return attrs

    def validate_items(self, items):
        if not hasattr(self, '_order'):
            return items
        order_item_ids = set(str(oi.id) for oi in self._order.items.all())
        validated = []
        seen = set()
        has_used_or_damaged = False
        delivered_at = self._order.delivered_at or self._order.updated_at
        days_since_delivery = max(0, (timezone.now() - delivered_at).days)
        for entry in items:
            oi_id = str(entry.get('order_item_id', ''))
            if not oi_id:
                raise serializers.ValidationError('Cada ítem debe tener order_item_id.')
            if oi_id not in order_item_ids:
                raise serializers.ValidationError(f'Ítem {oi_id} no pertenece a la orden.')
            if oi_id in seen:
                raise serializers.ValidationError('Ítems duplicados en la solicitud.')
            seen.add(oi_id)
            qty = int(entry.get('quantity', 1))
            if qty < 1:
                raise serializers.ValidationError('La cantidad debe ser al menos 1.')
            order_item = self._order.items.get(pk=oi_id)
            if qty > order_item.quantity:
                raise serializers.ValidationError(
                    f'No puedes devolver más unidades ({qty}) de las compradas ({order_item.quantity}).'
                )
            condition = entry.get('condition', 'unused')
            has_original_packaging = bool(entry.get('has_original_packaging', True))
            if condition == 'unused' and not has_original_packaging:
                raise serializers.ValidationError(
                    'Para condición "Sin uso" se requiere empaque original.'
                )
            if condition in ('used', 'damaged'):
                has_used_or_damaged = True
            validated.append({
                'order_item': order_item,
                'quantity':   qty,
                'condition':  condition,
                'has_original_packaging': has_original_packaging,
            })
        if has_used_or_damaged and days_since_delivery > RETURN_WINDOW_DAYS_USED:
            raise serializers.ValidationError(
                f'Para productos usados/dañados el plazo máximo es de {RETURN_WINDOW_DAYS_USED} días.'
            )
        if not has_used_or_damaged and days_since_delivery > RETURN_WINDOW_DAYS_NEW:
            raise serializers.ValidationError(
                f'Para productos nuevos el plazo máximo es de {RETURN_WINDOW_DAYS_NEW} días.'
            )
        return validated

    def create(self, validated_data):
        from django.db import transaction
        user  = self.context['request'].user
        order = self._order
        items = validated_data.pop('items')

        parent = getattr(self, '_parent_return', None)
        attempt_number = (parent.attempt_number + 1) if parent else 1
        note_create = 'Solicitud creada por el cliente.'
        if parent:
            note_create = (
                f'Solicitud creada por el cliente (reintento, solicitud anterior {parent.return_code}).'
            )

        with transaction.atomic():
            return_request = ReturnRequest.objects.create(
                user             = user,
                order            = order,
                parent_return    = parent,
                attempt_number   = attempt_number,
                reason           = validated_data['reason'],
                reason_detail    = validated_data.get('reason_detail', ''),
                customer_notes   = validated_data.get('customer_notes', ''),
                refund_method    = validated_data.get('refund_method', ''),
                estimated_refund_at=timezone.now(),
            )
            for item_data in items:
                ReturnItem.objects.create(
                    return_request        = return_request,
                    order_item            = item_data['order_item'],
                    quantity              = item_data['quantity'],
                    condition             = item_data['condition'],
                    has_original_packaging= item_data['has_original_packaging'],
                )
            ReturnAuditLog.objects.create(
                return_request = return_request,
                from_status    = '',
                to_status      = 'requested',
                changed_by     = user,
                note           = note_create,
            )
            if parent:
                parent.transition(
                    'closed',
                    changed_by=user,
                    note='Cliente inició una nueva solicitud de devolución.',
                )
        return return_request
