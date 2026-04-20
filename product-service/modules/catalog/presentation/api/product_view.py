from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from ...application.services.product_service import ProductService
from ...infrastructure.models import Product
from ...infrastructure.repositories.product_repository_impl import DjangoProductRepository
from ..serializers import ProductSerializer


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    service = ProductService(DjangoProductRepository())

    def get_queryset(self):
        return Product.objects.apply_filters(self.request.query_params)

    @action(detail=False, methods=['get'])
    def search(self, request):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({'count': queryset.count(), 'results': serializer.data})

    @action(detail=False, methods=['get'])
    def by_category(self, request):
        category = request.query_params.get('category')
        if not category:
            return Response({'error': 'category parameter required'}, status=status.HTTP_400_BAD_REQUEST)
        queryset = self.get_queryset().filter(category__slug=category)
        return Response(self.get_serializer(queryset, many=True).data)

    @action(detail=False, methods=['get'])
    def by_type(self, request):
        product_type = request.query_params.get('type') or request.query_params.get('product_type')
        if not product_type:
            return Response({'error': 'type parameter required'}, status=status.HTTP_400_BAD_REQUEST)
        queryset = self.get_queryset().filter(product_type__slug=product_type)
        return Response(self.get_serializer(queryset, many=True).data)

    @action(detail=True, methods=['patch'])
    def update_price(self, request, pk=None):
        product = self.get_object()
        product.price = request.data.get('price', product.price)
        product.save(update_fields=['price', 'updated_at'])
        return Response({'status': 'price updated', 'new_price': product.price})

    @action(detail=True, methods=['patch'])
    def update_product(self, request, pk=None):
        product = self.get_object()
        serializer = self.get_serializer(product, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({'status': 'product updated', 'data': serializer.data})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'])
    def update_stock(self, request, pk=None):
        product = self.get_object()
        stock = request.data.get('stock')
        if stock is None:
            return Response({'error': 'stock parameter required'}, status=status.HTTP_400_BAD_REQUEST)
        product.stock = int(stock)
        product.save(update_fields=['stock', 'updated_at'])
        return Response({'status': 'stock updated', 'new_stock': product.stock})
