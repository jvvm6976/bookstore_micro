from rest_framework import serializers
from .models import Customer, Address, Job

class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = [
            'id',
            'customer',
            'label',
            'recipient_name',
            'phone_number',
            'street',
            'ward',
            'city',
            'country',
            'is_default',
        ]
        read_only_fields = ['id', 'customer']

class JobSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = '__all__'

class CustomerSerializer(serializers.ModelSerializer):
    default_address = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Customer
        fields = [
            'id',
            'username',
            'email',
            'password',
            'first_name',
            'last_name',
            'phone_number',
            'address',
            'job',
            'cart_id',
            'default_address',
        ]
        extra_kwargs = {
            'password': {'write_only': True, 'required': False},
            'id': {'read_only': True},
        }
        
    def create(self, validated_data):
        user = Customer.objects.create_user(**validated_data)
        return user
    
    def update(self, instance, validated_data):
        """Update customer profile, handle password separately"""
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance

    def get_default_address(self, instance):
        addr = instance.addresses.filter(is_default=True).first()
        if not addr:
            return None
        return AddressSerializer(addr).data
    
    def to_representation(self, instance):
        """Ensure all fields are properly serialized in response"""
        rep = super().to_representation(instance)
        # Explicitly ensure username is included
        if 'username' not in rep:
            rep['username'] = instance.username
        return rep


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True, min_length=6)
    confirm_password = serializers.CharField(required=True, write_only=True, min_length=6)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'Xac nhan mat khau khong khop'})
        return attrs