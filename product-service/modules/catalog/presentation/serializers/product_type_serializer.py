from rest_framework import serializers

from ...infrastructure.models import ProductType


class ProductTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductType
        fields = ['id', 'slug', 'name', 'icon']
