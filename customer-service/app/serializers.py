from rest_framework import serializers
from .models import Customer, Address, Job

class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = '__all__'

class JobSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = '__all__'

class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['id', 'username', 'email', 'password', 'first_name', 'last_name', 'address', 'job', 'cart_id']
        extra_kwargs = {'password': {'write_only': True, 'required': False}}
        
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