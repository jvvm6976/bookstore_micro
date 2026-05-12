import logging
from rest_framework import viewsets, generics, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import ValidationError
from .models import Notification, NotificationLog
from .serializers import NotificationSerializer, NotificationLogSerializer

logger = logging.getLogger(__name__)


class NotificationListView(generics.ListAPIView):
    """
    Get user's notifications
    GET /notifications/
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = NotificationSerializer
    
    def get_queryset(self):
        return Notification.objects.filter(user_id=self.request.user.id).order_by('-created_at')


class NotificationDetailView(generics.RetrieveAPIView):
    """
    Get notification detail
    GET /notifications/{id}/
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = NotificationSerializer
    queryset = Notification.objects.all()


class NotificationUnreadListView(generics.ListAPIView):
    """
    Get unread notifications
    GET /notifications/unread/
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = NotificationSerializer
    
    def get_queryset(self):
        return Notification.objects.filter(
            user_id=self.request.user.id,
            status='unread'
        ).order_by('-created_at')


class NotificationMarkReadView(generics.UpdateAPIView):
    """
    Mark notification as read
    PUT /notifications/{id}/read/
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = NotificationSerializer
    queryset = Notification.objects.all()
    
    def update(self, request, *args, **kwargs):
        notification = self.get_object()
        notification.status = 'read'
        notification.save()
        
        serializer = self.get_serializer(notification)
        return Response(serializer.data, status=status.HTTP_200_OK)


class NotificationMarkAllReadView(generics.GenericAPIView):
    """
    Mark all notifications as read
    PUT /notifications/read-all/
    """
    permission_classes = (IsAuthenticated,)
    
    def put(self, request, *args, **kwargs):
        Notification.objects.filter(
            user_id=request.user.id,
            status='unread'
        ).update(status='read')
        
        return Response(
            {'message': 'All notifications marked as read'},
            status=status.HTTP_200_OK
        )


# Internal APIs

class InternalNotificationCreateView(generics.CreateAPIView):
    """
    Internal API - Create notification (called from other services)
    POST /internal/notifications/
    
    Request: {user_id, title, content, type, status}
    Response: {id, user_id, title, content, type, status, created_at, updated_at}
    """
    permission_classes = (AllowAny,)
    serializer_class = NotificationSerializer
    
    def create(self, request, *args, **kwargs):
        user_id = request.data.get('user_id')
        title = request.data.get('title')
        content = request.data.get('content')
        notif_type = request.data.get('type')
        notif_status = request.data.get('status', 'unread')
        
        # Validation
        if not all([user_id, title, content, notif_type]):
            raise ValidationError({
                'error': 'user_id, title, content, type are required'
            })
        
        if notif_status not in ['unread', 'read']:
            raise ValidationError({'error': 'Invalid status'})
        
        if notif_type not in ['order', 'payment', 'shipping', 'system']:
            raise ValidationError({'error': 'Invalid type'})
        
        try:
            notification = Notification.objects.create(
                user_id=user_id,
                title=title,
                content=content,
                type=notif_type,
                status=notif_status
            )
            
            # Log notification
            NotificationLog.objects.create(
                notification=notification,
                channel='system',
                result='success'
            )
            
            serializer = NotificationSerializer(notification)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error creating notification: {str(e)}")
            return Response(
                {'error': f'Failed to create notification: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
