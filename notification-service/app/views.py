import logging
from django.db.models import Q
from rest_framework import viewsets, generics, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import ValidationError, PermissionDenied
from .models import Notification, NotificationLog, NotificationReadState
from .serializers import NotificationSerializer, NotificationLogSerializer

logger = logging.getLogger(__name__)

STAFF_ROLES = {'admin', 'manager', 'staff'}
RECIPIENT_TYPES = {'customer', 'staff', 'admin', 'manager', 'all'}
NOTIFICATION_TYPES = {'order', 'payment', 'shipping', 'review', 'system'}
NOTIFICATION_STATUSES = {'unread', 'read'}
PRIORITIES = {'low', 'normal', 'high'}


def _role_name(user):
    return getattr(user, 'role', None)


def _assert_staff(user):
    if _role_name(user) not in STAFF_ROLES:
        raise PermissionDenied('Only staff can manage notifications')


def _recipient_types_for_role(role):
    if role == 'admin':
        return {'admin', 'manager', 'staff', 'all'}
    if role == 'manager':
        return {'manager', 'staff', 'all'}
    if role == 'staff':
        return {'staff', 'all'}
    return {'all'}


def _visible_notification_query(user):
    role = _role_name(user)
    direct_query = Q(user_id=user.id)
    role_query = Q(recipient_type__in=_recipient_types_for_role(role)) & (
        Q(target_role__isnull=True) | Q(target_role='') | Q(target_role=role)
    )
    return direct_query | role_query


def _visible_notifications(user):
    return (
        Notification.objects
        .filter(_visible_notification_query(user))
        .prefetch_related('read_states')
        .distinct()
    )


def _mark_notification_read(notification, user):
    if notification.user_id == user.id:
        notification.status = 'read'
        notification.save(update_fields=['status', 'updated_at'])
        return

    NotificationReadState.objects.update_or_create(
        notification=notification,
        user_id=user.id,
        defaults={'status': 'read'},
    )


class NotificationListView(generics.ListAPIView):
    """
    Get user's notifications
    GET /notifications/
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = NotificationSerializer
    
    def get_queryset(self):
        if self.request.query_params.get('scope') == 'manage' and _role_name(self.request.user) in STAFF_ROLES:
            return Notification.objects.prefetch_related('read_states').all().order_by('-created_at')
        return _visible_notifications(self.request.user).order_by('-created_at')


class NotificationDetailView(generics.RetrieveAPIView):
    """
    Get notification detail
    GET /notifications/{id}/
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return _visible_notifications(self.request.user)


class NotificationManageView(generics.GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = NotificationSerializer

    def get_object(self):
        _assert_staff(self.request.user)
        try:
            return Notification.objects.get(pk=self.kwargs.get('pk'))
        except Notification.DoesNotExist:
            raise ValidationError({'error': 'Notification not found'})

    def get(self, request, *args, **kwargs):
        notification = self.get_object()
        return Response(self.get_serializer(notification).data)

    def patch(self, request, *args, **kwargs):
        notification = self.get_object()
        allowed = {
            'user_id', 'recipient_type', 'target_role', 'title', 'content',
            'type', 'entity_type', 'entity_id', 'priority', 'status'
        }
        for field, value in request.data.items():
            if field in allowed:
                setattr(notification, field, value)
        if notification.recipient_type not in RECIPIENT_TYPES:
            raise ValidationError({'error': 'Invalid recipient_type'})
        if notification.type not in NOTIFICATION_TYPES:
            raise ValidationError({'error': 'Invalid type'})
        if notification.priority not in PRIORITIES:
            raise ValidationError({'error': 'Invalid priority'})
        if notification.status not in NOTIFICATION_STATUSES:
            raise ValidationError({'error': 'Invalid status'})
        if notification.recipient_type == 'customer' and not notification.user_id:
            raise ValidationError({'error': 'user_id is required for customer notifications'})
        notification.save()
        return Response(self.get_serializer(notification).data)

    def delete(self, request, *args, **kwargs):
        notification = self.get_object()
        notification.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class NotificationUnreadListView(generics.ListAPIView):
    """
    Get unread notifications
    GET /notifications/unread/
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = NotificationSerializer
    
    def get_queryset(self):
        user = self.request.user
        return (
            _visible_notifications(user)
            .filter(
                Q(user_id=user.id, status='unread') |
                (~Q(user_id=user.id) & ~Q(read_states__user_id=user.id, read_states__status='read'))
            )
            .order_by('-created_at')
            .distinct()
        )


class NotificationMarkReadView(generics.UpdateAPIView):
    """
    Mark notification as read
    PUT /notifications/{id}/read/
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return _visible_notifications(self.request.user)
    
    def update(self, request, *args, **kwargs):
        notification = self.get_object()
        _mark_notification_read(notification, request.user)
        
        serializer = self.get_serializer(notification)
        return Response(serializer.data, status=status.HTTP_200_OK)


class NotificationMarkAllReadView(generics.GenericAPIView):
    """
    Mark all notifications as read
    PUT /notifications/read-all/
    """
    permission_classes = (IsAuthenticated,)
    
    def put(self, request, *args, **kwargs):
        user = request.user
        visible = _visible_notifications(user)
        visible.filter(user_id=user.id, status='unread').update(status='read')

        role_notifications = visible.exclude(user_id=user.id)
        for notification in role_notifications.exclude(
            read_states__user_id=user.id,
            read_states__status='read'
        ):
            _mark_notification_read(notification, user)
        
        return Response(
            {'message': 'All notifications marked as read'},
            status=status.HTTP_200_OK
        )


# Internal APIs

class InternalNotificationCreateView(generics.CreateAPIView):
    """
    Internal API - Create notification (called from other services)
    POST /internal/notifications/
    
    Request: {user_id?, recipient_type, target_role?, title, content, type, status}
    Response: {id, user_id, recipient_type, title, content, type, status, created_at, updated_at}
    """
    permission_classes = (AllowAny,)
    serializer_class = NotificationSerializer
    
    def create(self, request, *args, **kwargs):
        user_id = request.data.get('user_id')
        recipient_type = request.data.get('recipient_type', 'customer')
        target_role = request.data.get('target_role')
        title = request.data.get('title')
        content = request.data.get('content')
        notif_type = request.data.get('type')
        notif_status = request.data.get('status', 'unread')
        entity_type = request.data.get('entity_type')
        entity_id = request.data.get('entity_id')
        priority = request.data.get('priority', 'normal')
        
        # Validation
        if not all([title, content, notif_type]):
            raise ValidationError({
                'error': 'title, content, type are required'
            })

        if recipient_type not in RECIPIENT_TYPES:
            raise ValidationError({'error': 'Invalid recipient_type'})

        if recipient_type == 'customer' and not user_id:
            raise ValidationError({'error': 'user_id is required for customer notifications'})
        
        if notif_status not in NOTIFICATION_STATUSES:
            raise ValidationError({'error': 'Invalid status'})
        
        if notif_type not in NOTIFICATION_TYPES:
            raise ValidationError({'error': 'Invalid type'})

        if priority not in PRIORITIES:
            raise ValidationError({'error': 'Invalid priority'})

        if user_id in ['', None]:
            user_id = None
        
        try:
            notification = Notification.objects.create(
                user_id=user_id,
                recipient_type=recipient_type,
                target_role=target_role,
                title=title,
                content=content,
                type=notif_type,
                entity_type=entity_type,
                entity_id=entity_id,
                priority=priority,
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
