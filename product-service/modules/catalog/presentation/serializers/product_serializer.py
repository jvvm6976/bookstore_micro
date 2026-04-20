from rest_framework import serializers

from ...infrastructure.models import Product
from .brand_serializer import BrandSerializer
from .category_serializer import CategorySerializer
from .product_type_serializer import ProductTypeSerializer
from .variant_serializer import ProductVariantSerializer


class ProductSerializer(serializers.ModelSerializer):
    title = serializers.CharField(source='name', required=False)
    type_detail = ProductTypeSerializer(source='product_type', read_only=True)
    category_detail = CategorySerializer(source='category', read_only=True)
    brand_detail = BrandSerializer(source='brand', read_only=True)
    publisher_detail = BrandSerializer(source='brand', read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'slug', 'name', 'title', 'author', 'product_type', 'type_detail',
            'category', 'category_detail', 'brand', 'brand_detail', 'publisher_detail',
            'price', 'stock', 'description', 'cover_image_url', 'attributes',
            'is_active', 'created_at', 'updated_at', 'variants'
        ]
