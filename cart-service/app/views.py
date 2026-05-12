import logging
import requests
from rest_framework import viewsets, generics, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import ValidationError
from django.db import transaction
from .models import Cart, CartItem, Wishlist, WishlistItem
from .serializers import CartSerializer, CartItemSerializer, WishlistSerializer, WishlistItemSerializer

logger = logging.getLogger(__name__)

PRODUCT_SERVICE_URL = 'http://product-service:8000'


class CartDetailView(generics.RetrieveAPIView):
    """
    Get user's cart
    GET /cart/
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = CartSerializer
    
    def get_object(self):
        cart, _ = Cart.objects.get_or_create(user_id=self.request.user.id)
        return cart


class CartAddItemView(generics.CreateAPIView):
    """
    Add item to cart
    POST /cart/add/
    
    Request: {product_id, quantity}
    Response: {id, user_id, items, created_at, updated_at}
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = CartSerializer
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        user_id = request.user.id
        product_id = request.data.get('product_id')
        quantity = request.data.get('quantity', 1)
        
        # Validation
        if not product_id:
            raise ValidationError({'error': 'product_id is required'})
        
        try:
            quantity = int(quantity)
            if quantity <= 0:
                raise ValidationError({'error': 'Quantity must be greater than 0'})
        except (ValueError, TypeError):
            raise ValidationError({'error': 'Invalid quantity'})
        
        # Get product price from Product Service
        try:
            prod_resp = requests.get(
                f"{PRODUCT_SERVICE_URL}/internal/products/{product_id}/price/",
                timeout=5
            )
            if prod_resp.status_code == 200:
                unit_price = prod_resp.json().get('unit_price')
            else:
                raise ValidationError({'error': 'Product not found'})
        except requests.RequestException as e:
            logger.error(f"Error calling product service: {str(e)}")
            raise ValidationError({'error': 'Failed to get product price'})
        
        # Get or create cart
        cart, _ = Cart.objects.get_or_create(user_id=user_id)
        
        # If item exists, increment quantity; otherwise create new
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product_id=product_id,
            defaults={'quantity': quantity, 'unit_price': unit_price}
        )
        
        if not created:
            cart_item.quantity += quantity
            cart_item.unit_price = unit_price  # Update to latest price
            cart_item.save()
        
        serializer = CartSerializer(cart)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CartUpdateItemView(generics.UpdateAPIView):
    """
    Update item quantity in cart
    PUT /cart/update/
    
    Request: {product_id, quantity}
    Response: {id, user_id, items, created_at, updated_at}
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = CartSerializer
    
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        user_id = request.user.id
        product_id = request.data.get('product_id')
        quantity = request.data.get('quantity')
        
        # Validation
        if not product_id or quantity is None:
            raise ValidationError({'error': 'product_id and quantity are required'})
        
        try:
            quantity = int(quantity)
        except (ValueError, TypeError):
            raise ValidationError({'error': 'Invalid quantity'})
        
        try:
            cart = Cart.objects.get(user_id=user_id)
            cart_item = CartItem.objects.get(cart=cart, product_id=product_id)
            if quantity <= 0:
                cart_item.delete()
                serializer = CartSerializer(cart)
                return Response(serializer.data, status=status.HTTP_200_OK)

            cart_item.quantity = quantity
            cart_item.save()
            
            serializer = CartSerializer(cart)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except (Cart.DoesNotExist, CartItem.DoesNotExist):
            raise ValidationError({'error': 'Item not found in cart'})


class CartRemoveItemView(generics.DestroyAPIView):
    """
    Remove item from cart
    DELETE /cart/items/{product_id}/
    """
    permission_classes = (IsAuthenticated,)
    
    def destroy(self, request, *args, **kwargs):
        user_id = request.user.id
        product_id = self.kwargs.get('pk')
        
        try:
            cart = Cart.objects.get(user_id=user_id)
            cart_item = CartItem.objects.get(cart=cart, product_id=product_id)
            cart_item.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except (Cart.DoesNotExist, CartItem.DoesNotExist):
            raise ValidationError({'error': 'Item not found in cart'})


class CartClearView(generics.GenericAPIView):
    """
    Clear all items from cart
    DELETE /cart/clear/
    """
    permission_classes = (IsAuthenticated,)
    
    def delete(self, request, *args, **kwargs):
        user_id = request.user.id
        try:
            cart = Cart.objects.get(user_id=user_id)
            cart.items.all().delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Cart.DoesNotExist:
            raise ValidationError({'error': 'Cart not found'})


class WishlistDetailView(generics.RetrieveAPIView):
    """
    Get user's wishlist
    GET /wishlist/
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = WishlistSerializer
    
    def get_object(self):
        wishlist, _ = Wishlist.objects.get_or_create(user_id=self.request.user.id)
        return wishlist


class WishlistAddItemView(generics.CreateAPIView):
    """
    Add item to wishlist
    POST /wishlist/add/
    
    Request: {product_id}
    Response: {id, user_id, items, created_at, updated_at}
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = WishlistSerializer
    
    def create(self, request, *args, **kwargs):
        user_id = request.user.id
        product_id = request.data.get('product_id')
        
        if not product_id:
            raise ValidationError({'error': 'product_id is required'})
        
        wishlist, _ = Wishlist.objects.get_or_create(user_id=user_id)
        WishlistItem.objects.get_or_create(wishlist=wishlist, product_id=product_id)
        
        serializer = WishlistSerializer(wishlist)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class WishlistRemoveItemView(generics.DestroyAPIView):
    """
    Remove item from wishlist
    DELETE /wishlist/items/{product_id}/
    """
    permission_classes = (IsAuthenticated,)
    
    def destroy(self, request, *args, **kwargs):
        user_id = request.user.id
        product_id = self.kwargs.get('pk')
        
        try:
            wishlist = Wishlist.objects.get(user_id=user_id)
            item = WishlistItem.objects.get(wishlist=wishlist, product_id=product_id)
            item.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except (Wishlist.DoesNotExist, WishlistItem.DoesNotExist):
            raise ValidationError({'error': 'Item not found in wishlist'})


class WishlistMoveToCartView(generics.GenericAPIView):
    """
    Move item from wishlist to cart
    PUT /wishlist/move-to-cart/
    
    Request: {product_id}
    Response: {id, user_id, items, created_at, updated_at}
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = CartSerializer
    
    @transaction.atomic
    def put(self, request, *args, **kwargs):
        user_id = request.user.id
        product_id = request.data.get('product_id')
        
        if not product_id:
            raise ValidationError({'error': 'product_id is required'})
        
        # Check if item exists in wishlist
        try:
            wishlist = Wishlist.objects.get(user_id=user_id)
            wishlist_item = WishlistItem.objects.get(wishlist=wishlist, product_id=product_id)
        except (Wishlist.DoesNotExist, WishlistItem.DoesNotExist):
            raise ValidationError({'error': 'Item not found in wishlist'})
        
        # Get product price
        try:
            prod_resp = requests.get(
                f"{PRODUCT_SERVICE_URL}/internal/products/{product_id}/price/",
                timeout=5
            )
            if prod_resp.status_code == 200:
                unit_price = prod_resp.json().get('unit_price')
            else:
                raise ValidationError({'error': 'Product not found'})
        except requests.RequestException as e:
            logger.error(f"Error calling product service: {str(e)}")
            raise ValidationError({'error': 'Failed to get product price'})
        
        # Add to cart
        cart, _ = Cart.objects.get_or_create(user_id=user_id)
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product_id=product_id,
            defaults={'quantity': 1, 'unit_price': unit_price}
        )
        
        if not created:
            cart_item.quantity += 1
            cart_item.unit_price = unit_price
            cart_item.save()
        
        # Remove from wishlist
        wishlist_item.delete()
        
        serializer = CartSerializer(cart)
        return Response(serializer.data, status=status.HTTP_200_OK)


# Internal APIs

class InternalCartDetailView(generics.RetrieveAPIView):
    """
    Internal API - Get user's cart
    GET /internal/carts/{user_id}/
    """
    permission_classes = (AllowAny,)
    serializer_class = CartSerializer
    
    def get_object(self):
        user_id = self.kwargs.get('user_id')
        cart, _ = Cart.objects.get_or_create(user_id=user_id)
        return cart


class InternalCartClearView(generics.GenericAPIView):
    """
    Internal API - Clear user's cart
    DELETE /internal/carts/{user_id}/clear/
    """
    permission_classes = (AllowAny,)
    
    def delete(self, request, *args, **kwargs):
        user_id = self.kwargs.get('user_id')
        try:
            cart = Cart.objects.get(user_id=user_id)
            cart.items.all().delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Cart.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
