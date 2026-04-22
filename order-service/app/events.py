"""
Event Bus – RabbitMQ publisher/consumer (pika).
Falls back gracefully if RabbitMQ is unavailable.
"""
import json
import logging
import os
import threading

logger = logging.getLogger(__name__)

RABBITMQ_URL = os.getenv('RABBITMQ_URL', 'amqp://guest:guest@rabbitmq:5672/')

EXCHANGE = 'ecommerce'
ROUTING_KEYS = {
    'order.created':   'order.created',
    'order.paid':      'order.paid',
    'order.canceled':  'order.canceled',
    'order.shipped':   'order.shipped',
}


def _get_channel():
    try:
        import pika
        params = pika.URLParameters(RABBITMQ_URL)
        params.socket_timeout = 3
        conn = pika.BlockingConnection(params)
        ch = conn.channel()
        ch.exchange_declare(exchange=EXCHANGE, exchange_type='topic', durable=True)
        return conn, ch
    except Exception as e:
        logger.warning('RabbitMQ unavailable: %s', e)
        return None, None


def publish(routing_key: str, payload: dict):
    """Publish an event. Non-blocking; silently drops if broker is down."""
    def _send():
        conn, ch = _get_channel()
        if ch is None:
            return
        try:
            import pika
            ch.basic_publish(
                exchange=EXCHANGE,
                routing_key=routing_key,
                body=json.dumps(payload),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # persistent
                    content_type='application/json',
                ),
            )
            logger.info('Event published: %s', routing_key)
        except Exception as e:
            logger.warning('Failed to publish event %s: %s', routing_key, e)
        finally:
            try:
                conn.close()
            except Exception:
                pass
    threading.Thread(target=_send, daemon=True).start()


def publish_order_created(order, items):
    publish('order.created', {
        'order_id': order.id,
        'customer_id': order.customer_id,
        'total_amount': float(order.total_amount),
        'items': items,
    })


def publish_order_paid(order):
    publish('order.paid', {
        'order_id': order.id,
        'customer_id': order.customer_id,
        'total_amount': float(order.total_amount),
    })


def publish_order_canceled(order):
    publish('order.canceled', {
        'order_id': order.id,
        'customer_id': order.customer_id,
    })
