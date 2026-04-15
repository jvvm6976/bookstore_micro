from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from .models import Book, Publisher
from .serializers import BookSerializer, PublisherSerializer, UpdatePriceSerializer, UpdateBookSerializer

class PublisherViewSet(viewsets.ModelViewSet):
    queryset = Publisher.objects.all()
    serializer_class = PublisherSerializer

class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.all()
    serializer_class = BookSerializer

    def get_queryset(self):
        """Filter books based on query parameters"""
        queryset = Book.objects.all()
        
        # Search by title, author, or category
        search_term = self.request.query_params.get('search', None)
        if search_term:
            queryset = queryset.filter(
                Q(title__icontains=search_term) |
                Q(author__icontains=search_term)
            )
        
        # Filter by category
        category = self.request.query_params.get('category', None)
        if category:
            queryset = queryset.filter(category=category)
        
        # Filter by publisher
        publisher = self.request.query_params.get('publisher', None)
        if publisher:
            queryset = queryset.filter(publisher__name__icontains=publisher)
        
        return queryset

    @action(detail=False, methods=['get'])
    def search(self, request):
        """Search books by title, author, or category"""
        search_term = request.query_params.get('q', '')
        category = request.query_params.get('category', None)
        min_price = request.query_params.get('min_price', None)
        max_price = request.query_params.get('max_price', None)

        queryset = Book.objects.all()
        
        if search_term:
            queryset = queryset.filter(
                Q(title__icontains=search_term) |
                Q(author__icontains=search_term) |
                Q(category__icontains=search_term)
            )
        
        if category:
            queryset = queryset.filter(category=category)
        
        if min_price:
            queryset = queryset.filter(price__gte=float(min_price))
        
        if max_price:
            queryset = queryset.filter(price__lte=float(max_price))

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'count': len(queryset),
            'results': serializer.data
        })

    @action(detail=False, methods=['get'])
    def by_category(self, request):
        """Get all books in a specific category"""
        category = request.query_params.get('category', None)
        if not category:
            return Response({'error': 'category parameter required'}, status=status.HTTP_400_BAD_REQUEST)
        
        books = Book.objects.filter(category=category)
        serializer = self.get_serializer(books, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['patch'])
    def update_price(self, request, pk=None):
        """Update book price"""
        book = self.get_object()
        serializer = UpdatePriceSerializer(data=request.data)
        if serializer.is_valid():
            book.price = serializer.validated_data['price']
            book.save()
            return Response({'status': 'price updated', 'new_price': book.price})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'])
    def update_book(self, request, pk=None):
        """Update book details"""
        book = self.get_object()
        serializer = UpdateBookSerializer(book, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({'status': 'book updated', 'data': serializer.data})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'])
    def update_stock(self, request, pk=None):
        """Update book stock"""
        book = self.get_object()
        new_stock = request.data.get('stock')
        
        if new_stock is None:
            return Response({'error': 'stock parameter required'}, status=status.HTTP_400_BAD_REQUEST)
        
        book.stock = int(new_stock)
        book.save()
        return Response({'status': 'stock updated', 'new_stock': book.stock})