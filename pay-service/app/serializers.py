from rest_framework import serializers
from .models import Payment, PaymentStatus

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'order_id', 'amount', 'status', 'payment_method', 'transaction_id', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at', 'transaction_id']

class PaymentProcessSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    payment_method = serializers.CharField(max_length=50, default='credit_card')

class PaymentRefundSerializer(serializers.Serializer):
    payment_id = serializers.IntegerField()
    reason = serializers.CharField(max_length=255, required=False)
