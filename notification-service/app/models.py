from django.db import models
from django.utils import timezone

class Notification(models.Model):
    user_id = models.IntegerField(null=True, blank=True)
    recipient_type = models.CharField(max_length=50, default='customer')
    target_role = models.CharField(max_length=50, null=True, blank=True)
    title = models.CharField(max_length=255)
    content = models.TextField()
    type = models.CharField(max_length=50)
    entity_type = models.CharField(max_length=50, null=True, blank=True)
    entity_id = models.IntegerField(null=True, blank=True)
    priority = models.CharField(max_length=20, default='normal')
    status = models.CharField(max_length=50, default='unread')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'notifications'
        indexes = [
            models.Index(fields=['user_id', 'created_at']),
            models.Index(fields=['recipient_type', 'created_at']),
            models.Index(fields=['type', 'created_at']),
        ]


class NotificationReadState(models.Model):
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name='read_states')
    user_id = models.IntegerField()
    status = models.CharField(max_length=50, default='read')
    read_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'notification_read_states'
        unique_together = ('notification', 'user_id')

class NotificationLog(models.Model):
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name='logs')
    channel = models.CharField(max_length=50, null=True, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)
    result = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        db_table = 'notification_logs'
