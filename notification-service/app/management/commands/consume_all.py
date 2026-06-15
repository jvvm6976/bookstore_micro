import pika
import json
import os
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from app.models import Notification, NotificationLog

DEDUPLICATE_WINDOW_HOURS = 12

class Command(BaseCommand):
    help = 'Consume various events to create notifications'

    def handle(self, *args, **kwargs):
        rabbitmq_url = os.environ.get('RABBITMQ_URL', 'amqp://guest:guest@rabbitmq:5672/')
        params = pika.URLParameters(rabbitmq_url)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        
        queues = ['order_created', 'payment_success', 'shipment_created']
        for q in queues:
            channel.queue_declare(queue=q, durable=True)

        def callback(ch, method, properties, body):
            data = json.loads(body)
            order_id = data.get('order_id')
            user_id = data.get('user_id', 1)
            
            event_map = {
                'order_created': ('order', 'ShopSphere đã nhận đơn hàng', f'Đơn hàng #{order_id} đã được tạo. Bạn có thể thanh toán và theo dõi tiến trình trong mục Đơn hàng.'),
                'payment_success': ('payment', 'Thanh toán thành công', f'ShopSphere đã xác nhận thanh toán cho đơn hàng #{order_id}.'),
                'shipment_created': ('shipping', 'Vận đơn mới', f'Đơn hàng #{order_id} đã có vận đơn mới. ShopSphere sẽ cập nhật khi đơn bắt đầu giao.'),
            }
            notif_type, title, content = event_map.get(
                method.routing_key,
                ('system', f"Event: {method.routing_key}", f"Event {method.routing_key} occurred for Order {order_id}")
            )
            
            fields = {
                'user_id': user_id,
                'recipient_type': 'customer',
                'target_role': None,
                'title': title,
                'content': content,
                'type': notif_type,
                'entity_type': 'order',
                'entity_id': order_id,
                'priority': 'normal',
                'status': 'unread',
            }
            noti = (
                Notification.objects
                .filter(created_at__gte=timezone.now() - timedelta(hours=DEDUPLICATE_WINDOW_HOURS), **fields)
                .order_by('-created_at')
                .first()
            )
            result = 'deduplicated'
            if not noti:
                noti = Notification.objects.create(**fields)
                result = 'success'
            NotificationLog.objects.create(
                notification=noti,
                channel='system',
                result=result
            )
            self.stdout.write(f"Notification created for {method.routing_key}")
            ch.basic_ack(delivery_tag=method.delivery_tag)

        channel.basic_qos(prefetch_count=1)
        for q in queues:
            channel.basic_consume(queue=q, on_message_callback=callback)
            
        self.stdout.write('Waiting for events in Notification Service...')
        channel.start_consuming()
