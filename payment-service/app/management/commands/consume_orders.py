import pika
import json
import os
from django.core.management.base import BaseCommand
from app.models import Payment, PaymentTransaction
from app.rabbitmq_client import publish_event

class Command(BaseCommand):
    help = 'Consume order_created events'

    def handle(self, *args, **kwargs):
        rabbitmq_url = os.environ.get('RABBITMQ_URL', 'amqp://guest:guest@rabbitmq:5672/')
        params = pika.URLParameters(rabbitmq_url)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.queue_declare(queue='order_created', durable=True)

        def callback(ch, method, properties, body):
            data = json.loads(body)
            order_id = data.get('order_id')
            amount = data.get('amount')
            self.stdout.write(f"Received order_created: {order_id}")
            
            # Simulated payment logic, idempotent with manual payment endpoint.
            payment, created = Payment.objects.get_or_create(
                order_id=order_id,
                defaults={
                    'amount': amount,
                    'payment_method': 'vnpay',
                    'overall_status': 'success'
                }
            )
            if not created and payment.overall_status != 'success':
                payment.overall_status = 'success'
                payment.save(update_fields=['overall_status', 'updated_at'])
            PaymentTransaction.objects.get_or_create(
                transaction_code=f'TXN-{order_id}-{payment.id}',
                defaults={
                    'payment': payment,
                    'transaction_note': 'System auto-pay via Saga',
                }
            )

            # Publish payment_success
            publish_event('payment_success', {'order_id': order_id, 'payment_id': payment.id})
            
            ch.basic_ack(delivery_tag=method.delivery_tag)

        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(queue='order_created', on_message_callback=callback)
        self.stdout.write('Waiting for order_created events...')
        channel.start_consuming()
