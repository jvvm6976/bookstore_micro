from rest_framework import viewsets

from ...infrastructure.models import ProductType
from ..serializers import ProductTypeSerializer


class ProductTypeViewSet(viewsets.ModelViewSet):
    queryset = ProductType.objects.all()
    serializer_class = ProductTypeSerializer
