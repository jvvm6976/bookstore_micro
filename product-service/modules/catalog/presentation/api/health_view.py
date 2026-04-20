from rest_framework.decorators import api_view
from rest_framework.response import Response

from ...infrastructure.models import Product


@api_view(['GET'])
def health(request):
    try:
        return Response({'service': 'product-service', 'status': 'healthy', 'products': Product.objects.count()})
    except Exception as exc:
        return Response({'service': 'product-service', 'status': 'unhealthy', 'error': str(exc)}, status=503)
