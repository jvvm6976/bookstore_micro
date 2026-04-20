import os
import requests
from django.db.models import Avg, Count
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Comment
from .serializers import CommentCreateSerializer, CommentSerializer


ORDER_SERVICE_URL = os.getenv('ORDER_SERVICE_URL', 'http://order-service:8000')
PAID_STATUSES = {'paid', 'shipped'}

class CommentViewSet(viewsets.ModelViewSet):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer

    def get_serializer_class(self):
        if self.action == 'create':
            return CommentCreateSerializer
        return CommentSerializer

    def _get_paid_orders(self, customer_id):
        url = f"{ORDER_SERVICE_URL}/api/orders/by_customer/"
        resp = requests.get(url, params={'customer_id': customer_id}, timeout=8)
        if resp.status_code != 200:
            return None
        data = resp.json()
        orders = data.get('orders', [])
        return [o for o in orders if str(o.get('status', '')).lower() in PAID_STATUSES]

    def _eligible_order_ids(self, customer_id, book_id):
        orders = self._get_paid_orders(customer_id)
        if orders is None:
            return None
        eligible = []
        for order in orders:
            oid = order.get('id')
            for item in order.get('items', []) or []:
                if int(item.get('book_id', 0) or 0) == int(book_id):
                    eligible.append(int(oid))
                    break
        return eligible

    def create(self, request, *args, **kwargs):
        """
        Create review with strict policy:
        - Must have purchased book
        - One review per (customer, book, order)
        - If order_id omitted, auto-pick an eligible not-yet-reviewed order
        """
        serializer = CommentCreateSerializer(data=request.data)
        if serializer.is_valid():
            customer_id = serializer.validated_data['customer_id']
            book_id = serializer.validated_data['book_id']
            requested_order_id = serializer.validated_data.get('order_id')

            try:
                eligible_order_ids = self._eligible_order_ids(customer_id, book_id)
            except requests.exceptions.RequestException:
                eligible_order_ids = None

            if eligible_order_ids is None:
                return Response(
                    {'error': 'Cannot verify purchase at this time. Please try again.'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

            if not eligible_order_ids:
                return Response(
                    {'error': 'Bạn phải mua sản phẩm trước khi đánh giá.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

            if requested_order_id is not None:
                requested_order_id = int(requested_order_id)
                if requested_order_id not in eligible_order_ids:
                    return Response(
                        {'error': 'Đơn hàng không hợp lệ cho sản phẩm này hoặc chưa thanh toán.'},
                        status=status.HTTP_403_FORBIDDEN,
                    )
                order_id = requested_order_id
            else:
                reviewed_order_ids = set(
                    Comment.objects.filter(customer_id=customer_id, book_id=book_id).values_list('order_id', flat=True)
                )
                order_id = next((oid for oid in eligible_order_ids if oid not in reviewed_order_ids), None)
                if order_id is None:
                    return Response(
                        {'error': 'Bạn đã đánh giá sản phẩm này cho tất cả đơn mua hợp lệ.'},
                        status=status.HTTP_409_CONFLICT,
                    )

            if Comment.objects.filter(customer_id=customer_id, book_id=book_id, order_id=order_id).exists():
                return Response(
                    {'error': 'Sản phẩm này đã được bạn đánh giá trong đơn hàng đã chọn.'},
                    status=status.HTTP_409_CONFLICT,
                )

            comment = serializer.save(order_id=order_id)
            return Response(CommentSerializer(comment).data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def by_book(self, request):
        """Get all comments/reviews for a specific book"""
        book_id = request.query_params.get('book_id')
        if not book_id:
            return Response({'error': 'book_id parameter is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        comments = Comment.objects.filter(book_id=book_id).order_by('-created_at')
        serializer = CommentSerializer(comments, many=True)
        
        # Calculate average rating
        stats = Comment.objects.filter(book_id=book_id).aggregate(
            avg_rating=Avg('rating'),
            total_reviews=Count('id')
        )
        
        return Response({
            'book_id': book_id,
            'average_rating': round(stats['avg_rating'] or 0, 2),
            'total_reviews': stats['total_reviews'] or 0,
            'comments': serializer.data
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Bulk rating summary for product cards: /comments/summary/?book_ids=1,2,3"""
        raw = (request.query_params.get('book_ids') or '').strip()
        if not raw:
            return Response({'error': 'book_ids parameter is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            ids = [int(x) for x in raw.split(',') if x.strip()]
        except ValueError:
            return Response({'error': 'book_ids must be comma separated integers'}, status=status.HTTP_400_BAD_REQUEST)
        if not ids:
            return Response({'summaries': {}}, status=status.HTTP_200_OK)

        agg = (
            Comment.objects.filter(book_id__in=ids)
            .values('book_id')
            .annotate(avg_rating=Avg('rating'), total_reviews=Count('id'))
        )
        summaries = {str(i): {'average_rating': 0, 'total_reviews': 0} for i in ids}
        for row in agg:
            summaries[str(row['book_id'])] = {
                'average_rating': round(row['avg_rating'] or 0, 2),
                'total_reviews': row['total_reviews'] or 0,
            }
        return Response({'summaries': summaries}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def by_customer(self, request):
        """Get all comments submitted by a customer"""
        customer_id = request.query_params.get('customer_id')
        if not customer_id:
            return Response({'error': 'customer_id parameter is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        comments = Comment.objects.filter(customer_id=customer_id).order_by('-created_at')
        serializer = CommentSerializer(comments, many=True)
        
        return Response({
            'customer_id': customer_id,
            'count': comments.count(),
            'comments': serializer.data
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def book_rating_stats(self, request):
        """Get rating statistics for a book"""
        book_id = request.query_params.get('book_id')
        if not book_id:
            return Response({'error': 'book_id parameter is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        comments = Comment.objects.filter(book_id=book_id)
        
        # Calculate distribution
        rating_dist = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for comment in comments:
            rating_dist[comment.rating] += 1
        
        stats = comments.aggregate(
            avg_rating=Avg('rating'),
            total_reviews=Count('id')
        )
        
        return Response({
            'book_id': book_id,
            'average_rating': round(stats['avg_rating'] or 0, 2),
            'total_reviews': stats['total_reviews'] or 0,
            'rating_distribution': rating_dist,
            'percentage_by_rating': {
                rating: round((count / (stats['total_reviews'] or 1)) * 100, 1)
                for rating, count in rating_dist.items()
            }
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def filter_by_rating(self, request):
        """Get comments filtered by rating"""
        book_id = request.query_params.get('book_id')
        rating = request.query_params.get('rating')
        
        if not book_id or not rating:
            return Response({'error': 'book_id and rating parameters are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                return Response({'error': 'rating must be between 1 and 5'}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError:
            return Response({'error': 'rating must be an integer'}, status=status.HTTP_400_BAD_REQUEST)
        
        comments = Comment.objects.filter(book_id=book_id, rating=rating).order_by('-helpful_count')
        serializer = CommentSerializer(comments, many=True)
        
        return Response({
            'book_id': book_id,
            'rating': rating,
            'count': comments.count(),
            'comments': serializer.data
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['patch'])
    def mark_helpful(self, request, pk=None):
        """Mark a comment as helpful"""
        comment = self.get_object()
        comment.helpful_count += 1
        comment.save()

        return Response({
            'message': 'Comment marked as helpful',
            'comment': CommentSerializer(comment).data
        }, status=status.HTTP_200_OK)
