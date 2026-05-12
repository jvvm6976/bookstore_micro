from rest_framework import serializers
from .models import Shipment, ShipmentTracking


class ShipmentTrackingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShipmentTracking
        fields = ['id', 'location', 'status', 'updated_at']


class ShipmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shipment
        fields = ['id', 'order_id', 'receiver_name', 'phone', 'full_address', 'current_status', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ShipmentCreateSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()
    receiver_name = serializers.CharField(max_length=100)
    phone = serializers.CharField(max_length=20)
    full_address = serializers.CharField()


class ShipmentUpdateStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Shipment.STATUS_CHOICES)


class ShipmentAddTrackingSerializer(serializers.Serializer):
    location = serializers.CharField(max_length=255, required=False, allow_blank=True)
    status = serializers.CharField(max_length=50)
