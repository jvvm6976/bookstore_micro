import pika
import json
import os
from django.core.management.base import BaseCommand
from app.models import Notification, NotificationLog

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
            
            title = f"Event: {method.routing_key}"
            content = f"Event {method.routing_key} occurred for Order {order_id}"
            
            noti = Notification.objects.create(
                user_id=user_id,
                title=title,
                content=content,
                type=method.routing_key
            )
            NotificationLog.objects.create(
                notification=noti,
                channel='system',
                result='success'
            )
            self.stdout.write(f"Notification created for {method.routing_key}")
            ch.basic_ack(delivery_tag=method.delivery_tag)

        channel.basic_qos(prefetch_count=1)
        for q in queues:
            channel.basic_consume(queue=q, on_message_callback=callback)
            
        self.stdout.write('Waiting for events in Notification Service...')
        channel.start_consuming()
