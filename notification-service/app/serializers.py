from rest_framework import serializers
from .models import Notification, NotificationLog, NotificationReadState


class NotificationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationLog
        fields = ['id', 'channel', 'result', 'sent_at']


class NotificationSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            'id', 'user_id', 'recipient_type', 'target_role', 'title', 'content',
            'type', 'entity_type', 'entity_id', 'priority', 'status',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_status(self, obj):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        user_id = getattr(user, 'id', None)
        if not user_id:
            return obj.status

        if obj.user_id == user_id:
            return obj.status

        read_state = next(
            (state for state in obj.read_states.all() if state.user_id == user_id),
            None
        )
        return read_state.status if read_state else 'unread'


class NotificationReadStateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationReadState
        fields = ['id', 'notification', 'user_id', 'status', 'read_at']
