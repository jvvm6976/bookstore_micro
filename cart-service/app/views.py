import requests
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Cart, CartItem
from .serializers import CartSerializer, CartItemSerializer

class CartViewSet(viewsets.ModelViewSet):
    queryset = Cart.objects.all()
    serializer_class = CartSerializer

    @action(detail=True, methods=['post'])
    def add_item(self, request, pk=None):
        cart = self.get_object()
        book_id = request.data.get('book_id')
        quantity = int(request.data.get('quantity', 1))

        if not book_id:
            return Response({'error': 'book_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Call Product Service to get product details
        try:
            book_resp = requests.get(f'http://product-service:8000/api/books/{book_id}/')
            if book_resp.status_code != 200:
                return Response({'error': 'Book not found'}, status=status.HTTP_404_NOT_FOUND)
            
            book_data = book_resp.json()
            price = book_data.get('price')

            # Check stock
            if book_data.get('stock', 0) < quantity:
                return Response({'error': 'Not enough stock'}, status=status.HTTP_400_BAD_REQUEST)

        except requests.exceptions.RequestException as e:
            return Response({'error': 'Failed to communicate with Product Service'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        # Update or create CartItem
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart, 
            book_id=book_id,
            defaults={'price_at_add': price, 'quantity': quantity}
        )
        
        if not created:
            cart_item.quantity += quantity
            cart_item.price_at_add = price # Update to latest price
            cart_item.save()

        return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def update_item_quantity(self, request, pk=None):
        cart = self.get_object()
        book_id = request.data.get('book_id')
        quantity = int(request.data.get('quantity', 0))

        try:
            item = CartItem.objects.get(cart=cart, book_id=book_id)
            if quantity <= 0:
                item.delete()
            else:
                try:
                    book_resp = requests.get(f'http://product-service:8000/api/books/{book_id}/')
                    if book_resp.status_code != 200:
                        return Response({'error': 'Book not found'}, status=status.HTTP_404_NOT_FOUND)
                    book_data = book_resp.json()
                    if int(book_data.get('stock', 0) or 0) < quantity:
                        return Response({'error': 'Not enough stock'}, status=status.HTTP_400_BAD_REQUEST)
                except requests.exceptions.RequestException:
                    return Response({'error': 'Failed to communicate with Product Service'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

                item.quantity = quantity
                item.save()
            return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)
        except CartItem.DoesNotExist:
            return Response({'error': 'Item not in cart'}, status=status.HTTP_404_NOT_FOUND)