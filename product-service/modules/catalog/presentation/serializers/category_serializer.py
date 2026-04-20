from rest_framework import serializers

from ...infrastructure.models import Category


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'slug', 'name', 'parent']
