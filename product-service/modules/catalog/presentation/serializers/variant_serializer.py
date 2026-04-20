from rest_framework import serializers

from ...infrastructure.models import ProductVariant


class ProductVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = ['id', 'sku', 'label', 'color', 'size', 'price_delta', 'stock', 'attributes']
