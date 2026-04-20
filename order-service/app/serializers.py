from rest_framework import serializers
from .models import Order, OrderItem

class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = '__all__'

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    
    class Meta:
        model = Order
        fields = [
            'id',
            'customer_id',
            'total_amount',
            'status',
            'created_at',
            'shipping_address',
            'shipping_phone',
            'shipping_address_id',
            'items',
        ]
