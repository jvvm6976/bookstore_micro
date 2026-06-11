from rest_framework import serializers
from django.conf import settings
from .models import Domain, Category, Product, Book, Electronics, Fashion

class DomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = Domain
        fields = ['id', 'name', 'description', 'created_at', 'updated_at']

class CategorySerializer(serializers.ModelSerializer):
    domain_name = serializers.CharField(source='domain.name', read_only=True)

    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'domain_id', 'domain_name', 'created_at', 'updated_at']
    
    def validate_domain_id(self, value):
        """Validate domain_id exists"""
        if not Domain.objects.filter(id=value).exists():
            raise serializers.ValidationError("Domain does not exist")
        return value

class BookSerializer(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = ['author', 'publisher', 'isbn']

class ElectronicsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Electronics
        fields = ['brand', 'warranty_months']

class FashionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fashion
        fields = ['size', 'color']

class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    domain_name = serializers.CharField(source='category.domain.name', read_only=True)
    domain_id = serializers.IntegerField(source='category.domain_id', read_only=True)
    
    # Nested data for specific product types
    book = BookSerializer(read_only=True)
    electronics = ElectronicsSerializer(read_only=True)
    fashion = FashionSerializer(read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'sku', 'price', 'stock', 'status',
            'category_id', 'category_name', 'domain_id', 'domain_name',
            'image_url', 'book', 'electronics', 'fashion',
            'created_at', 'updated_at'
        ]

    def validate_image_url(self, value):
        if not value:
            return value
        base_url = getattr(settings, 'PRODUCT_IMAGE_BASE_URL', '').rstrip('/')
        allowed_prefixes = tuple(prefix for prefix in [
            f'{base_url}/' if base_url else '',
            '/static/images/products/',
        ] if prefix)
        if value.startswith(allowed_prefixes):
            return value
        raise serializers.ValidationError('Ảnh sản phẩm phải được lưu trong thư mục local của Product Service.')
    
    def create(self, validated_data):
        """
        Tạo product với nested data (book, electronics, fashion)
        """
        # Extract nested data nếu được gửi
        book_data = self.initial_data.get('book')
        electronics_data = self.initial_data.get('electronics')
        fashion_data = self.initial_data.get('fashion')
        
        # Tạo product
        product = Product.objects.create(**validated_data)
        
        # Tạo nested data nếu có
        if book_data:
            Book.objects.create(product=product, **book_data)
        if electronics_data:
            Electronics.objects.create(product=product, **electronics_data)
        if fashion_data:
            Fashion.objects.create(product=product, **fashion_data)
        
        return product
    
    def update(self, instance, validated_data):
        """
        Cập nhật product với nested data
        """
        # Update product fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update nested data nếu được gửi
        book_data = self.initial_data.get('book')
        electronics_data = self.initial_data.get('electronics')
        fashion_data = self.initial_data.get('fashion')
        
        if book_data:
            book, created = Book.objects.get_or_create(product=instance)
            for attr, value in book_data.items():
                setattr(book, attr, value)
            book.save()
        
        if electronics_data:
            electronics, created = Electronics.objects.get_or_create(product=instance)
            for attr, value in electronics_data.items():
                setattr(electronics, attr, value)
            electronics.save()
        
        if fashion_data:
            fashion, created = Fashion.objects.get_or_create(product=instance)
            for attr, value in fashion_data.items():
                setattr(fashion, attr, value)
            fashion.save()
        
        return instance
