import logging
import os
import requests
from rest_framework import viewsets, generics, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from .models import Review, ReviewReply
from .serializers import ReviewSerializer, ReviewReplySerializer

logger = logging.getLogger(__name__)

ORDER_SERVICE_URL = os.environ.get('ORDER_SERVICE_URL', 'http://order-service:8000')
NOTIFICATION_SERVICE_URL = os.environ.get('NOTIFICATION_SERVICE_URL', 'http://notification-service:8000')

REVIEW_STATUSES = {'pending', 'approved', 'rejected'}


def _positive_int_query(params, name):
    value = params.get(name)
    if value in (None, ''):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValidationError({'error': f'{name} must be a positive integer'})
    if parsed <= 0:
        raise ValidationError({'error': f'{name} must be a positive integer'})
    return parsed


def _is_staff_user(user):
    return getattr(user, 'role', None) in {'admin', 'manager', 'staff'}


def _assert_staff_user(user):
    if not getattr(user, 'is_authenticated', False) or not _is_staff_user(user):
        raise PermissionDenied('Only staff can moderate reviews')


def _send_notification(payload):
    try:
        requests.post(
            f"{NOTIFICATION_SERVICE_URL}/internal/notifications/",
            json=payload,
            timeout=5
        )
    except Exception as e:
        logger.warning(f"Warning: Failed to send notification: {str(e)}")


def _notify_customer(user_id, title, content, review_id, priority='normal'):
    _send_notification({
        'user_id': user_id,
        'recipient_type': 'customer',
        'title': title,
        'content': content,
        'type': 'review',
        'entity_type': 'review',
        'entity_id': review_id,
        'priority': priority,
        'status': 'unread',
    })


def _notify_staff(title, content, review_id, priority='normal'):
    _send_notification({
        'recipient_type': 'staff',
        'title': title,
        'content': content,
        'type': 'review',
        'entity_type': 'review',
        'entity_id': review_id,
        'priority': priority,
        'status': 'unread',
    })


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
            if int(order_data.get('user_id') or 0) != int(user_id):
                raise ValidationError({'error': 'You can only review your own orders'})
            order_status = order_data.get('current_status')
            if order_status not in ['completed', 'paid', 'delivered']:
                raise ValidationError({'error': f'You can only review completed or paid orders (current status: {order_status})'})
            ordered_product_ids = {
                int(item.get('product_id'))
                for item in order_data.get('items', [])
                if item.get('product_id') is not None
            }
            if int(product_id) not in ordered_product_ids:
                raise ValidationError({'error': 'You can only review products from this order'})
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

        _notify_customer(
            user_id,
            'Đánh giá đang chờ duyệt',
            f'Đánh giá của bạn cho sản phẩm #{product_id} đã được ghi nhận và đang chờ duyệt',
            review.id,
        )
        _notify_staff(
            'Đánh giá mới cần duyệt',
            f'Khách hàng #{user_id} vừa gửi đánh giá {rating_val} sao cho sản phẩm #{product_id}',
            review.id,
            priority='high',
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
    def get_queryset(self):
        if _is_staff_user(self.request.user):
            queryset = Review.objects.all()
        else:
            queryset = Review.objects.filter(status='approved')
        product_id = _positive_int_query(self.request.query_params, 'product_id')
        if product_id is not None:
            queryset = queryset.filter(product_id=product_id)
        order_id = _positive_int_query(self.request.query_params, 'order_id')
        if order_id is not None:
            queryset = queryset.filter(order_id=order_id)
        review_status = self.request.query_params.get('status')
        if review_status:
            if review_status not in REVIEW_STATUSES:
                raise ValidationError({'error': 'Invalid status'})
            queryset = queryset.filter(status=review_status)
        return queryset.order_by('-created_at')

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
        
        is_owner = review.user_id == request.user.id
        is_staff = _is_staff_user(request.user)
        if not (is_owner or is_staff):
            raise PermissionDenied('You can only update your own reviews')
        
        rating = request.data.get('rating')
        comment = request.data.get('comment')
        review_status = request.data.get('status')
        
        if rating is not None:
            if not is_owner:
                raise PermissionDenied('Only review owner can edit rating')
            try:
                rating_val = int(rating)
                if rating_val < 1 or rating_val > 5:
                    raise ValidationError({'error': 'Rating must be between 1 and 5'})
                review.rating = rating_val
            except (ValueError, TypeError):
                raise ValidationError({'error': 'Rating must be an integer'})
        
        if comment is not None:
            if not is_owner:
                raise PermissionDenied('Only review owner can edit comment')
            review.comment = comment

        if review_status is not None:
            if not is_staff:
                raise PermissionDenied('Only staff can moderate reviews')
            if review_status not in REVIEW_STATUSES:
                raise ValidationError({'error': 'Invalid status'})
            review.status = review_status
        elif is_owner and (rating is not None or comment is not None):
            # Owner edits should be moderated again before becoming public.
            review.status = 'pending'
        
        review.save()
        if review_status is not None:
            status_labels = {
                'approved': 'đã được duyệt',
                'rejected': 'đã bị từ chối',
                'pending': 'đang chờ duyệt',
            }
            _notify_customer(
                review.user_id,
                'Trạng thái đánh giá đã cập nhật',
                f'Đánh giá #{review.id} {status_labels.get(review.status, review.status)}',
                review.id,
                priority='high' if review.status in {'approved', 'rejected'} else 'normal',
            )
        serializer = self.get_serializer(review)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def destroy(self, request, *args, **kwargs):
        review = self.get_object()
        
        if review.user_id != request.user.id and not _is_staff_user(request.user):
            raise PermissionDenied('You can only delete your own reviews')
        
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
        try:
            order_resp = requests.get(f"{ORDER_SERVICE_URL}/internal/orders/{order_id}/", timeout=5)
            if order_resp.status_code != 200:
                return Review.objects.none()
            order_data = order_resp.json()
            if int(order_data.get('user_id') or 0) != int(self.request.user.id) and not _is_staff_user(self.request.user):
                raise PermissionDenied('You can only view reviews for your own orders')
        except requests.RequestException:
            return Review.objects.none()
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
        _assert_staff_user(request.user)
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

            _notify_customer(
                review.user_id,
                'Có phản hồi cho đánh giá của bạn',
                f'Nhân viên đã phản hồi đánh giá #{review.id}',
                review.id,
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

            _notify_staff(
                'Đánh giá mới cần duyệt',
                f'Khách hàng #{user_id} vừa gửi đánh giá {rating_val} sao cho sản phẩm #{product_id}',
                review.id,
                priority='high',
            )
            
            serializer = ReviewSerializer(review)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error creating review: {str(e)}")
            return Response(
                {'error': f'Failed to create review: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
