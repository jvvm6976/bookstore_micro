import logging
import requests
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Order, OrderItem, OrderStatus
from .serializers import OrderSerializer, OrderItemSerializer
from .saga import OrderSaga
from .events import publish_order_created, publish_order_paid, publish_order_canceled

logger = logging.getLogger(__name__)
CART_SVC = 'http://cart-service:8000'


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all().order_by('-created_at')
    serializer_class = OrderSerializer

    @action(detail=False, methods=['post'])
    def checkout(self, request):
        """Saga-orchestrated checkout."""
        customer_id     = request.data.get('customer_id')
        cart_id         = request.data.get('cart_id')
        shipping_address = request.data.get('shipping_address', '')
        payment_method  = request.data.get('payment_method', 'credit_card')

        if not customer_id or not cart_id:
            return Response({'error': 'customer_id and cart_id are required'}, status=400)

        # 1. Fetch cart
        try:
            cart_resp = requests.get(f'{CART_SVC}/api/carts/{cart_id}/', timeout=10)
            if cart_resp.status_code != 200:
                return Response({'error': 'Cart not found'}, status=404)
            cart_data = cart_resp.json()
        except requests.RequestException as e:
            return Response({'error': f'Cart service unavailable: {e}'}, status=503)

        items = cart_data.get('items', [])
        if not items:
            return Response({'error': 'Cart is empty'}, status=400)

        # 2. Create order (PENDING)
        total = sum(float(i.get('price_at_add', 0)) * i.get('quantity', 1) for i in items)
        order = Order.objects.create(
            customer_id=customer_id,
            total_amount=total,
            shipping_address=shipping_address,
            status=OrderStatus.PENDING,
        )
        for i in items:
            OrderItem.objects.create(
                order=order,
                book_id=i['book_id'],
                quantity=i['quantity'],
                price=i.get('price_at_add', 0),
            )

        saga_items = [{'book_id': i['book_id'], 'quantity': i['quantity'], 'price': i.get('price_at_add', 0)} for i in items]

        # Publish event: order created
        publish_order_created(order, saga_items)

        # 3. Run saga
        saga = OrderSaga(
            order=order,
            items=saga_items,
            cart_id=cart_id,
            payment_method=payment_method,
            shipping_address=shipping_address,
        )
        result = saga.execute()

        order.refresh_from_db()
        if result['success']:
            publish_order_paid(order)
        else:
            publish_order_canceled(order)
        http_status = status.HTTP_201_CREATED if result['success'] else status.HTTP_402_PAYMENT_REQUIRED
        return Response({
            'success': result['success'],
            'message': 'Order placed successfully' if result['success'] else result.get('error', 'Checkout failed'),
            'order': OrderSerializer(order).data,
            'saga_steps': result.get('steps', []),
        }, status=http_status)

    @action(detail=False, methods=['get'])
    def by_customer(self, request):
        customer_id = request.query_params.get('customer_id')
        if not customer_id:
            return Response({'error': 'customer_id required'}, status=400)
        orders = Order.objects.filter(customer_id=customer_id).order_by('-created_at')
        return Response({'customer_id': customer_id, 'count': orders.count(), 'orders': OrderSerializer(orders, many=True).data})

    @action(detail=True, methods=['get'])
    def order_details(self, request, pk=None):
        order = self.get_object()
        return Response({'order': OrderSerializer(order).data})

    @action(detail=False, methods=['post'])
    def verify_purchase(self, request):
        customer_id = request.data.get('customer_id')
        book_id     = request.data.get('book_id')
        if not customer_id or not book_id:
            return Response({'error': 'customer_id and book_id required'}, status=400)
        items = OrderItem.objects.filter(
            order__customer_id=customer_id,
            order__status=OrderStatus.PAID,
            book_id=book_id,
        )
        return Response({'customer_id': customer_id, 'book_id': book_id, 'purchased': items.exists()})

    @action(detail=True, methods=['post'])
    def cancel_order(self, request, pk=None):
        order = self.get_object()

        role = (
            request.headers.get('X-User-Role')
            or request.META.get('HTTP_X_USER_ROLE')
            or ''
        ).strip().lower()
        service_user_id = (
            request.headers.get('X-Service-User-Id')
            or request.META.get('HTTP_X_SERVICE_USER_ID')
        )
        try:
            service_user_id = int(service_user_id) if service_user_id is not None else None
        except (TypeError, ValueError):
            service_user_id = None

        if order.status in (OrderStatus.CANCELED, OrderStatus.SHIPPED):
            return Response({'error': f'Cannot cancel order in status: {order.status}'}, status=400)

        # Customer can only cancel their own order and only while pending.
        if role == 'customer':
            if service_user_id != order.customer_id:
                return Response({'error': 'You can only cancel your own orders'}, status=403)
            if order.status != OrderStatus.PENDING:
                return Response({'error': 'Only pending orders can be canceled by customer'}, status=400)

        # Staff/manager/admin are allowed to cancel pending/paid orders.
        # If already paid, trigger refund best-effort.
        if order.status == OrderStatus.PAID:
            try:
                pay_lookup = requests.get(
                    'http://pay-service:8000/api/payments/by_order/',
                    params={'order_id': order.id},
                    timeout=8,
                )
                if pay_lookup.status_code == 200:
                    payment = pay_lookup.json()
                    payment_id = payment.get('id')
                    if payment_id:
                        requests.post(
                            f'http://pay-service:8000/api/payments/{payment_id}/refund/',
                            json={},
                            timeout=8,
                        )
            except requests.RequestException:
                logger.warning('Refund request failed for order %s', order.id)

        order.status = OrderStatus.CANCELED
        order.save()
        return Response({'message': 'Order canceled', 'order': OrderSerializer(order).data})

    # ── health ────────────────────────────────────────────────────────────────
    @action(detail=False, methods=['get'])
    def health(self, request):
        return Response({'service': 'order-service', 'status': 'healthy'})
