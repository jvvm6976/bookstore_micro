from rest_framework import serializers
from .models import Payment, PaymentTransaction


class PaymentTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentTransaction
        fields = ['id', 'transaction_note', 'transaction_code', 'created_at']


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'order_id', 'amount', 'overall_status', 'payment_method', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class PaymentProcessSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    payment_method = serializers.ChoiceField(
        choices=['vnpay', 'momo', 'cod', 'stripe'],
        default='cod'
    )
    transaction_note = serializers.CharField(max_length=500, required=False, allow_blank=True)


class PaymentRefundSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255, required=False)
