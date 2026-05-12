import pika
import json
import os
from django.core.management.base import BaseCommand
from app.models import Shipment, ShipmentTracking
from app.rabbitmq_client import publish_event

class Command(BaseCommand):
    help = 'Consume payment_success events to create shipment'

    def handle(self, *args, **kwargs):
        rabbitmq_url = os.environ.get('RABBITMQ_URL', 'amqp://guest:guest@rabbitmq:5672/')
        params = pika.URLParameters(rabbitmq_url)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.queue_declare(queue='payment_success', durable=True)

        def callback(ch, method, properties, body):
            data = json.loads(body)
            order_id = data.get('order_id')
            self.stdout.write(f"Received payment_success: {order_id}")
            
            shipment, _ = Shipment.objects.get_or_create(
                order_id=order_id,
                defaults={
                    'receiver_name': 'Mock User',
                    'phone': '0123456789',
                    'full_address': 'Mock Address via Saga',
                    'current_status': 'processing'
                }
            )
            ShipmentTracking.objects.get_or_create(
                shipment=shipment,
                status='processing',
                defaults={'location': 'Warehouse'}
            )

            publish_event('shipment_created', {'order_id': order_id, 'shipment_id': shipment.id})
            
            ch.basic_ack(delivery_tag=method.delivery_tag)

        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(queue='payment_success', on_message_callback=callback)
        self.stdout.write('Waiting for payment_success events...')
        channel.start_consuming()
