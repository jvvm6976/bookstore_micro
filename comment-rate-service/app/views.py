import logging
import requests
from rest_framework import viewsets, generics, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import ValidationError
from django.db import transaction
from .models import Review, ReviewReply
from .serializers import ReviewSerializer, ReviewReplySerializer

logger = logging.getLogger(__name__)

ORDER_SERVICE_URL = 'http://order-service:8000'


def _create_review(request):
    user_id = request.user.id
    order_id = request.data.get('order_id')
    product_id = request.data.get('product_id')
    rating = request.data.get('rating')
    comment = request.data.get('comment', '')

    # Validation
    if not all([order_id, product_id, rating]):
        raise ValidationError({'error': 'order_id, product_id, rating are required'})

    try:
        rating_val = int(rating)
        if rating_val < 1 or rating_val > 5:
            raise ValidationError({'error': 'Rating must be between 1 and 5'})
    except (ValueError, TypeError):
        raise ValidationError({'error': 'Rating must be an integer'})

    # Check if already reviewed (UNIQUE constraint)
    if Review.objects.filter(user_id=user_id, order_id=order_id, product_id=product_id).exists():
        raise ValidationError({'error': 'You have already reviewed this product for this order'})

    # Validate order status = completed or paid
    try:
        order_resp = requests.get(f"{ORDER_SERVICE_URL}/internal/orders/{order_id}/", timeout=5)
        if order_resp.status_code == 200:
            order_data = order_resp.json()
            order_status = order_data.get('current_status')
            if order_status not in ['completed', 'paid', 'delivered']:
                raise ValidationError({'error': f'You can only review completed or paid orders (current status: {order_status})'})
        else:
            raise ValidationError({'error': 'Order not found'})
    except requests.RequestException as e:
        logger.error(f"Error calling order service: {str(e)}")
        raise ValidationError({'error': 'Failed to validate order'})

    try:
        review = Review.objects.create(
            user_id=user_id,
            order_id=order_id,
            product_id=product_id,
            rating=rating_val,
            comment=comment,
            status='pending'  # Default to pending, needs approval
        )

        serializer = ReviewSerializer(review)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.error(f"Error creating review: {str(e)}")
        return Response(
            {'error': f'Failed to create review: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class ReviewListView(generics.ListCreateAPIView):
    """
    Get all reviews (paginated, only approved)
    GET /reviews/
    """
    permission_classes = (AllowAny,)
    serializer_class = ReviewSerializer
    queryset = Review.objects.filter(status='approved').order_by('-created_at')

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated()]
        return [AllowAny()]

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        return _create_review(request)


class ReviewCreateView(generics.CreateAPIView):
    """
    Create review (only for completed or paid orders)
    POST /reviews/
    
    Request: {order_id, product_id, rating, comment}
    Response: {id, user_id, order_id, product_id, rating, comment, status}
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = ReviewSerializer
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        return _create_review(request)


class ReviewDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Get/Update/Delete review
    GET /reviews/{id}/
    PUT /reviews/{id}/
    DELETE /reviews/{id}/
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = ReviewSerializer
    queryset = Review.objects.all()
    
    def update(self, request, *args, **kwargs):
        review = self.get_object()
        
        # Only owner or admin can update
        if review.user_id != request.user.id:
            raise ValidationError({'error': 'You can only update your own reviews'})
        
        rating = request.data.get('rating')
        comment = request.data.get('comment')
        
        if rating:
            try:
                rating_val = int(rating)
                if rating_val < 1 or rating_val > 5:
                    raise ValidationError({'error': 'Rating must be between 1 and 5'})
                review.rating = rating_val
            except (ValueError, TypeError):
                raise ValidationError({'error': 'Rating must be an integer'})
        
        if comment is not None:
            review.comment = comment
        
        review.save()
        serializer = self.get_serializer(review)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def destroy(self, request, *args, **kwargs):
        review = self.get_object()
        
        # Only owner or admin can delete
        if review.user_id != request.user.id:
            raise ValidationError({'error': 'You can only delete your own reviews'})
        
        review.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReviewMyListView(generics.ListAPIView):
    """
    Get current user's reviews
    GET /reviews/me/
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = ReviewSerializer
    
    def get_queryset(self):
        return Review.objects.filter(user_id=self.request.user.id).order_by('-created_at')


class ReviewByProductView(generics.ListAPIView):
    """
    Get reviews by product_id
    GET /reviews/products/{product_id}/
    """
    permission_classes = (AllowAny,)
    serializer_class = ReviewSerializer
    
    def get_queryset(self):
        product_id = self.kwargs.get('pk')
        return Review.objects.filter(product_id=product_id, status='approved').order_by('-created_at')


class ReviewByOrderView(generics.ListAPIView):
    """
    Get reviews by order_id
    GET /reviews/orders/{order_id}/
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = ReviewSerializer
    
    def get_queryset(self):
        order_id = self.kwargs.get('pk')
        return Review.objects.filter(order_id=order_id).order_by('-created_at')


class ReviewReplyCreateView(generics.CreateAPIView):
    """
    Add reply to review (admin/staff only)
    POST /reviews/{id}/reply/
    
    Request: {content}
    Response: {id, review_id, user_id, content, created_at}
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = ReviewReplySerializer
    
    def create(self, request, *args, **kwargs):
        review_id = self.kwargs.get('pk')
        content = request.data.get('content')
        
        if not content:
            raise ValidationError({'error': 'content is required'})
        
        try:
            review = Review.objects.get(id=review_id)
        except Review.DoesNotExist:
            raise ValidationError({'error': 'Review not found'})
        
        try:
            reply = ReviewReply.objects.create(
                review=review,
                user_id=request.user.id,
                content=content
            )
            
            serializer = ReviewReplySerializer(reply)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error creating reply: {str(e)}")
            return Response(
                {'error': f'Failed to create reply: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Internal APIs

class InternalReviewCreateView(generics.CreateAPIView):
    """
    Internal API - Create review (called from Order Service)
    POST /internal/reviews/
    
    Request: {user_id, order_id, product_id, rating, comment}
    Response: {id, user_id, order_id, product_id, rating, comment, status}
    """
    permission_classes = (AllowAny,)
    serializer_class = ReviewSerializer
    
    def create(self, request, *args, **kwargs):
        user_id = request.data.get('user_id')
        order_id = request.data.get('order_id')
        product_id = request.data.get('product_id')
        rating = request.data.get('rating')
        comment = request.data.get('comment', '')
        
        # Validation
        if not all([user_id, order_id, product_id, rating]):
            raise ValidationError({'error': 'user_id, order_id, product_id, rating are required'})
        
        try:
            rating_val = int(rating)
            if rating_val < 1 or rating_val > 5:
                raise ValidationError({'error': 'Rating must be between 1 and 5'})
        except (ValueError, TypeError):
            raise ValidationError({'error': 'Rating must be an integer'})
        
        # Check if already reviewed
        if Review.objects.filter(user_id=user_id, order_id=order_id, product_id=product_id).exists():
            raise ValidationError({'error': 'Review already exists for this product in this order'})
        
        try:
            review = Review.objects.create(
                user_id=user_id,
                order_id=order_id,
                product_id=product_id,
                rating=rating_val,
                comment=comment,
                status='pending'
            )
            
            serializer = ReviewSerializer(review)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error creating review: {str(e)}")
            return Response(
                {'error': f'Failed to create review: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
