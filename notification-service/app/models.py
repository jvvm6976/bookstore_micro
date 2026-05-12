from django.db import models

class Notification(models.Model):
    user_id = models.IntegerField()
    title = models.CharField(max_length=255)
    content = models.TextField()
    type = models.CharField(max_length=50)
    status = models.CharField(max_length=50, default='unread')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'notifications'

class NotificationLog(models.Model):
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name='logs')
    channel = models.CharField(max_length=50, null=True, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)
    result = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        db_table = 'notification_logs'
