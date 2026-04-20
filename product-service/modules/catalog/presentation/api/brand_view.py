from rest_framework import viewsets

from ...infrastructure.models import Brand
from ..serializers import BrandSerializer


class BrandViewSet(viewsets.ModelViewSet):
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer
