from django.urls import path
from .views import (
    NotificationListView,
    NotificationDetailView,
    NotificationUnreadListView,
    NotificationMarkReadView,
    NotificationMarkAllReadView,
    InternalNotificationCreateView
)

urlpatterns = [
    # Client APIs
    path('notifications/', NotificationListView.as_view(), name='notification-list'),
    path('notifications/<int:pk>/', NotificationDetailView.as_view(), name='notification-detail'),
    path('notifications/unread/', NotificationUnreadListView.as_view(), name='notification-unread'),
    path('notifications/<int:pk>/read/', NotificationMarkReadView.as_view(), name='notification-mark-read'),
    path('notifications/read-all/', NotificationMarkAllReadView.as_view(), name='notification-mark-all-read'),
    
    # Internal APIs
    path('internal/notifications/', InternalNotificationCreateView.as_view(), name='internal-notification-create'),
]
