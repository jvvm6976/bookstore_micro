from rest_framework import serializers
from .models import Shipment, ShipmentStatus

class ShipmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shipment
        fields = ['id', 'order_id', 'status', 'shipping_address', 'tracking_number', 'shipping_method', 'estimated_delivery', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at', 'tracking_number']

class ShipmentCreateSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()
    customer_id = serializers.IntegerField(required=False)
    address = serializers.CharField(max_length=500)
    shipping_method = serializers.CharField(max_length=50, default='standard')

class ShipmentUpdateStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=ShipmentStatus.choices)
