from rest_framework import serializers

from ...infrastructure.models import Brand


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ['id', 'slug', 'name', 'country']
