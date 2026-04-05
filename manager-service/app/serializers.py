from rest_framework import serializers
from .models import Manager, InventoryLog, SalesReport


class ManagerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Manager
        fields = ['id', 'name', 'email', 'department', 'is_active', 'created_at']
        extra_kwargs = {'password': {'write_only': True}}


class InventoryLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryLog
        fields = '__all__'


class SalesReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalesReport
        fields = '__all__'
