from rest_framework import serializers
from .models import BookCatalog, SearchHistory


class BookCatalogSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookCatalog
        fields = '__all__'


class SearchHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SearchHistory
        fields = '__all__'
