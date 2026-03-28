from django.conf import settings
from rest_framework import serializers

from .models import LoyaltyAccount, PointTransaction


class LoyaltyAccountSerializer(serializers.ModelSerializer):
    balance_in_cop = serializers.SerializerMethodField(
        help_text='Equivalencia del saldo en COP.'
    )
    point_value_cop = serializers.SerializerMethodField(
        help_text='Valor en COP de 1 punto.'
    )
    points_per_cop = serializers.SerializerMethodField(
        help_text='COP necesarios para ganar 1 punto.'
    )

    class Meta:
        model = LoyaltyAccount
        fields = [
            'points_balance',
            'total_earned',
            'total_redeemed',
            'balance_in_cop',
            'point_value_cop',
            'points_per_cop',
            'updated_at',
        ]
        read_only_fields = fields

    def get_point_value_cop(self, obj) -> int:
        return getattr(settings, 'LOYALTY_POINT_VALUE_COP', 10)

    def get_points_per_cop(self, obj) -> int:
        return getattr(settings, 'LOYALTY_POINTS_PER_COP', 1000)

    def get_balance_in_cop(self, obj) -> int:
        return obj.points_balance * getattr(settings, 'LOYALTY_POINT_VALUE_COP', 10)


class PointTransactionSerializer(serializers.ModelSerializer):
    transaction_type_display = serializers.CharField(
        source='get_transaction_type_display', read_only=True,
    )
    order_number = serializers.CharField(
        source='order.order_number', read_only=True, default=None,
    )

    class Meta:
        model = PointTransaction
        fields = [
            'id',
            'transaction_type',
            'transaction_type_display',
            'points',
            'balance_after',
            'order_number',
            'description',
            'created_at',
        ]
        read_only_fields = fields


class PointsPreviewSerializer(serializers.Serializer):
    points_to_use = serializers.IntegerField(min_value=1)
    order_total = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)
