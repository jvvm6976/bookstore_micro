from rest_framework import serializers
from .models import ActivityLog, Role, Shift, Staff

class StaffSerializer(serializers.ModelSerializer):
    class Meta:
        model = Staff
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role', 'department']

class StaffCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    role = serializers.ChoiceField(choices=Role.choices)
    
    class Meta:
        model = Staff
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'password', 'role', 'department']
        read_only_fields = ['id']
    
    def create(self, validated_data):
        user = Staff.objects.create_user(**validated_data)
        return user

class BookOperationSerializer(serializers.Serializer):
    operation = serializers.ChoiceField(choices=['create', 'update', 'delete', 'list'])
    book_data = serializers.JSONField()


class ActivityLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityLog
        fields = ['id', 'actor', 'action', 'resource_type', 'resource_id', 'message', 'meta', 'created_at']
        read_only_fields = ['id', 'created_at']


class ShiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shift
        fields = ['id', 'staff', 'start_time', 'end_time', 'status', 'notes', 'created_at']
        read_only_fields = ['id', 'created_at']
