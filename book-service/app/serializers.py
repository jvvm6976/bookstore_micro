from rest_framework import serializers
from .models import Book, Publisher, Category

class PublisherSerializer(serializers.ModelSerializer):
    class Meta:
        model = Publisher
        fields = '__all__'

class BookSerializer(serializers.ModelSerializer):
    publisher_detail = PublisherSerializer(source='publisher', read_only=True)
    
    class Meta:
        model = Book
        fields = ['id', 'title', 'author', 'publisher', 'publisher_detail', 'category', 'price', 'stock', 'description', 'cover_image_url']

class UpdatePriceSerializer(serializers.Serializer):
    price = serializers.DecimalField(max_digits=10, decimal_places=2)

class UpdateBookSerializer(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = ['title', 'author', 'publisher', 'category', 'stock']