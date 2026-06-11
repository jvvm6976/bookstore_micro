from rest_framework import viewsets, generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from .models import Order, OrderItem, OrderAddress, OrderStatusHistory
from .serializers import OrderSerializer, OrderItemSerializer, OrderAddressSerializer, OrderStatusHistorySerializer
from .rabbitmq_client import publish_event
from decimal import Decimal, InvalidOperation
import os
import requests
import logging

logger = logging.getLogger(__name__)

PRODUCT_SERVICE_URL = os.environ.get('PRODUCT_SERVICE_URL', 'http://product-service:8000')
USER_SERVICE_URL = os.environ.get('USER_SERVICE_URL', 'http://user-service:8000')
CART_SERVICE_URL = os.environ.get('CART_SERVICE_URL', 'http://cart-service:8000')
PAYMENT_SERVICE_URL = os.environ.get('PAYMENT_SERVICE_URL', 'http://payment-service:8000')
SHIPPING_SERVICE_URL = os.environ.get('SHIPPING_SERVICE_URL', 'http://shipping-service:8000')
NOTIFICATION_SERVICE_URL = os.environ.get('NOTIFICATION_SERVICE_URL', 'http://notification-service:8000')

ORDER_STATUSES = {'pending', 'paid', 'shipping', 'completed', 'cancelled', 'failed'}


def _send_notification(payload):
    try:
        requests.post(
            f"{NOTIFICATION_SERVICE_URL}/internal/notifications/",
            json=payload,
            timeout=5
        )
    except Exception as e:
        logger.warning(f"Warning: Failed to send notification: {str(e)}")


def _notify_customer(user_id, title, content, notif_type, entity_id=None, priority='normal'):
    _send_notification({
        'user_id': user_id,
        'recipient_type': 'customer',
        'title': title,
        'content': content,
        'type': notif_type,
        'entity_type': 'order',
        'entity_id': entity_id,
        'priority': priority,
        'status': 'unread',
    })


def _notify_staff(title, content, notif_type, entity_id=None, priority='normal'):
    _send_notification({
        'recipient_type': 'staff',
        'title': title,
        'content': content,
        'type': notif_type,
        'entity_type': 'order',
        'entity_id': entity_id,
        'priority': priority,
        'status': 'unread',
    })

class OrderCheckoutView(generics.CreateAPIView):
    """
    Checkout - Create order from cart
    POST /orders/checkout/
    
    Workflow:
    1. Get cart from Cart Service
    2. Get default address from User Service
    3. Lock prices from Product Service
    4. Check stock and reduce stock (atomic)
    5. Create Order, OrderItems, OrderAddress, OrderStatusHistory
    6. Clear cart
    7. Create Payment record
    8. Send notification
    9. Rollback on error (compensating transaction)
    """
    permission_classes = (IsAuthenticated,)
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        # 1. Get user_id from token
        user_id = request.user.id
        
        # 2. Get Cart
        try:
            cart_resp = requests.get(f"{CART_SERVICE_URL}/internal/carts/{user_id}/", timeout=5)
            if cart_resp.status_code != 200:
                raise ValidationError({'error': 'Cart not found or empty'})
            cart_data = cart_resp.json()
            cart_items = cart_data.get('items', [])
            if not cart_items:
                raise ValidationError({'error': 'Cart is empty'})
        except Exception as e:
            raise ValidationError({'error': f'Error calling cart service: {str(e)}'})

        # 3. Get Default Address
        try:
            addr_resp = requests.get(f"{USER_SERVICE_URL}/internal/users/{user_id}/default-address/", timeout=5)
            if addr_resp.status_code != 200:
                raise ValidationError({'error': 'Default address not found'})
            address_data = addr_resp.json()
        except Exception as e:
            raise ValidationError({'error': f'Error calling user service: {str(e)}'})

        total_price = Decimal('0')
        reduced_stocks = []  # Track items to rollback if needed
        
        try:
            # 4. Create Order
            order = Order.objects.create(
                user_id=user_id,
                total_price=0,  # will update later
                current_status='pending'
            )

            # 5. Lock Price & Check Stock from Product Service
            for item in cart_items:
                product_id = item['product_id']
                quantity = item['quantity']
                
                # Validate quantity
                if quantity <= 0:
                    raise ValidationError({'error': f'Invalid quantity for product {product_id}'})
                
                # Check stock first
                stock_resp = requests.get(f"{PRODUCT_SERVICE_URL}/internal/products/{product_id}/stock/", timeout=5)
                if stock_resp.status_code == 200:
                    stock = stock_resp.json().get('stock', 0)
                    if stock < quantity:
                        raise ValidationError({'error': f'Product {product_id} has insufficient stock ({stock} < {quantity})'})
                else:
                    raise ValidationError({'error': f'Product {product_id} stock check failed'})

                # Get price
                prod_resp = requests.get(f"{PRODUCT_SERVICE_URL}/internal/products/{product_id}/price/", timeout=5)
                if prod_resp.status_code == 200:
                    try:
                        unit_price = Decimal(str(prod_resp.json().get('unit_price')))
                    except (InvalidOperation, TypeError):
                        raise ValidationError({'error': f'Invalid price for product {product_id}'})
                else:
                    raise ValidationError({'error': f'Product {product_id} not found'})
                    
                # Reduce Stock (atomic)
                reduce_resp = requests.post(
                    f"{PRODUCT_SERVICE_URL}/internal/products/{product_id}/reduce-stock/",
                    json={"quantity": quantity},
                    timeout=5
                )
                if reduce_resp.status_code != 200:
                    raise ValidationError({'error': f'Failed to reduce stock for Product {product_id}'})
                
                # Add to tracking list for rollback
                reduced_stocks.append({'product_id': product_id, 'quantity': quantity})

                total_price += unit_price * quantity
                OrderItem.objects.create(
                    order=order,
                    product_id=product_id,
                    quantity=quantity,
                    unit_price=unit_price
                )

            order.total_price = total_price
            order.save()

            # 6. Save Snapshot Address
            OrderAddress.objects.create(
                order=order,
                receiver_name=address_data.get('receiver_name'),
                full_address=f"{address_data.get('street')}, {address_data.get('city')}",
                phone=address_data.get('phone')
            )

            # 7. Add Status History
            OrderStatusHistory.objects.create(
                order=order,
                status='pending'
            )

            # 8. Clear cart
            try:
                requests.delete(f"{CART_SERVICE_URL}/internal/carts/{user_id}/clear/", timeout=5)
            except Exception as e:
                logger.warning(f"Warning: Failed to clear cart for user {user_id}: {str(e)}")

            # 9. Create Shipment
            try:
                requests.post(
                    f"{SHIPPING_SERVICE_URL}/internal/shipments/",
                    json={
                        'order_id': order.id,
                        'receiver_name': address_data.get('receiver_name'),
                        'phone': address_data.get('phone'),
                        'full_address': f"{address_data.get('street')}, {address_data.get('city')}"
                    },
                    timeout=5
                )
            except Exception as e:
                logger.warning(f"Warning: Failed to create shipment for order {order.id}: {str(e)}")

            # 10. Publish Event
            publish_event('order_created', {
                'order_id': order.id,
                'user_id': user_id,
                'amount': str(total_price)
            })

            _notify_customer(
                user_id,
                'Đặt hàng thành công',
                f'Đơn hàng #{order.id} đã được tạo và đang chờ thanh toán',
                'order',
                entity_id=order.id,
            )
            _notify_staff(
                'Đơn hàng mới cần xử lý',
                f'Đơn hàng #{order.id} vừa được tạo, tổng tiền {total_price}',
                'order',
                entity_id=order.id,
                priority='high',
            )

            serializer = OrderSerializer(order)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except ValidationError as ve:
            # Rollback all reduced stocks
            for reduced_item in reduced_stocks:
                try:
                    requests.post(
                        f"{PRODUCT_SERVICE_URL}/internal/products/{reduced_item['product_id']}/increase-stock/",
                        json={"quantity": reduced_item['quantity']},
                        timeout=5
                    )
                except Exception as rollback_e:
                    logger.error(f"Critical Error: Failed to rollback stock for {reduced_item['product_id']} - {str(rollback_e)}")
            
            transaction.set_rollback(True)
            raise ve
        except Exception as e:
            # Rollback all reduced stocks
            for reduced_item in reduced_stocks:
                try:
                    requests.post(
                        f"{PRODUCT_SERVICE_URL}/internal/products/{reduced_item['product_id']}/increase-stock/",
                        json={"quantity": reduced_item['quantity']},
                        timeout=5
                    )
                except Exception as rollback_e:
                    logger.error(f"Critical Error: Failed to rollback stock for {reduced_item['product_id']} - {str(rollback_e)}")
            
            transaction.set_rollback(True)
            return Response(
                {'error': f'Checkout failed, transaction rolled back. Details: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Order Management
    GET /orders/ - List user's orders
    GET /orders/{id}/ - Get order detail
    GET /orders/{id}/history/ - Get order status history
    PUT /orders/{id}/cancel/ - Cancel order
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = OrderSerializer

    def get_queryset(self):
        if getattr(self.request.user, 'role', None) in {'admin', 'manager', 'staff'}:
            return Order.objects.all().order_by('-created_at')
        user_id = self.request.user.id
        return Order.objects.filter(user_id=user_id).order_by('-created_at')

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """Get order status history"""
        order = self.get_object()
        histories = OrderStatusHistory.objects.filter(order=order).order_by('-updated_at')
        serializer = OrderStatusHistorySerializer(histories, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['put'], url_path='status')
    @transaction.atomic
    def update_status(self, request, pk=None):
        if getattr(request.user, 'role', None) not in {'admin', 'manager', 'staff'}:
            raise PermissionDenied('Only staff can update order status')

        order = self.get_object()
        new_status = request.data.get('status')
        if new_status not in ORDER_STATUSES:
            raise ValidationError({'error': 'Invalid status'})

        transitions = {
            'pending': {'paid'},
            'paid': {'shipping'},
            'shipping': {'completed'},
            'completed': set(),
            'cancelled': set(),
            'failed': set(),
        }
        if new_status not in transitions.get(order.current_status, set()):
            raise ValidationError({
                'error': f'Cannot transition from {order.current_status} to {new_status}'
            })

        order.current_status = new_status
        order.save(update_fields=['current_status', 'updated_at'])
        OrderStatusHistory.objects.create(order=order, status=new_status)
        _notify_customer(
            order.user_id,
            'Trạng thái đơn hàng đã cập nhật',
            f'Đơn hàng #{order.id} đã chuyển sang trạng thái {new_status}',
            'order',
            entity_id=order.id,
        )
        return Response(self.get_serializer(order).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['put'])
    @transaction.atomic
    def cancel(self, request, pk=None):
        """
        Cancel order
        Only allow cancel if status is pending or paid
        """
        order = self.get_object()
        
        # Validate order status
        if order.current_status not in ['pending', 'paid']:
            raise ValidationError({
                'error': f'Order cannot be cancelled in {order.current_status} status'
            })
        
        old_status = order.current_status

        # Stock is reserved at checkout time, so every allowed cancellation must release it.
        for item in order.items.all():
            try:
                stock_resp = requests.post(
                    f"{PRODUCT_SERVICE_URL}/internal/products/{item.product_id}/increase-stock/",
                    json={"quantity": item.quantity},
                    timeout=5
                )
                if stock_resp.status_code >= 400:
                    raise ValidationError({
                        'error': f'Failed to rollback stock for product {item.product_id}'
                    })
            except requests.RequestException as e:
                logger.error(f"Error rolling back stock for product {item.product_id}: {str(e)}")
                raise ValidationError({
                    'error': f'Failed to rollback stock for product {item.product_id}'
                })

        # Change status after stock has been released.
        order.current_status = 'cancelled'
        order.save()

        # Add to history
        OrderStatusHistory.objects.create(
            order=order,
            status='cancelled'
        )

        refund_ok = False
        if old_status == 'paid':
            try:
                refund_resp = requests.post(
                    f"{PAYMENT_SERVICE_URL}/internal/payments/{order.id}/refund/",
                    json={'reason': 'Order cancelled'},
                    timeout=5
                )
                if refund_resp.status_code >= 400:
                    logger.warning("Failed to refund payment for order %s: %s", order.id, refund_resp.text)
                else:
                    refund_ok = True
            except requests.RequestException as e:
                logger.warning("Failed to call payment refund for order %s: %s", order.id, str(e))

        try:
            shipment_resp = requests.post(
                f"{SHIPPING_SERVICE_URL}/internal/shipments/{order.id}/cancel/",
                json={'location': 'Order cancelled'},
                timeout=5
            )
            if shipment_resp.status_code not in (200, 404):
                logger.warning("Failed to cancel shipment for order %s: %s", order.id, shipment_resp.text)
        except requests.RequestException as e:
            logger.warning("Failed to call shipment cancel for order %s: %s", order.id, str(e))

        _notify_customer(
            order.user_id,
            'Đơn hàng đã hủy',
            f'Đơn hàng #{order.id} đã được hủy thành công',
            'order',
            entity_id=order.id,
            priority='high',
        )
        if refund_ok:
            _notify_customer(
                order.user_id,
                'Hoàn tiền đã được ghi nhận',
                f'Thanh toán cho đơn hàng #{order.id} đã được chuyển sang trạng thái hoàn tiền',
                'payment',
                entity_id=order.id,
                priority='high',
            )
        _notify_staff(
            'Đơn hàng bị hủy',
            f'Đơn hàng #{order.id} đã bị hủy sau trạng thái {old_status}',
            'order',
            entity_id=order.id,
            priority='high',
        )

        return Response({'message': 'Order cancelled successfully'}, status=status.HTTP_200_OK)


# Internal APIs

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

@api_view(['PUT'])
@permission_classes([AllowAny])
def internal_order_status_update(request, order_id):
    """
    Internal API - Update order status
    PUT /internal/orders/{order_id}/status/
    
    Request: {status}
    Response: {id, user_id, current_status}
    """
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
    
    new_status = request.data.get('status')
    if not new_status:
        return Response({'error': 'status is required'}, status=status.HTTP_400_BAD_REQUEST)
    if new_status not in ORDER_STATUSES:
        return Response({'error': 'Invalid status'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Update order status
    order.current_status = new_status
    order.save()
    
    # Add to history
    OrderStatusHistory.objects.create(
        order=order,
        status=new_status
    )
    
    serializer = OrderSerializer(order)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def internal_order_detail(request, order_id):
    """
    Internal API - Get order detail
    GET /internal/orders/{order_id}/
    
    Response: {id, user_id, current_status, total_price}
    """
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
    
    serializer = OrderSerializer(order)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def internal_orders_by_customer(request):
    """
    Internal API - Get orders by customer/user ID
    GET /internal/orders/by_customer/?customer_id=1
    """
    customer_id = request.query_params.get('customer_id') or request.query_params.get('user_id')
    if not customer_id:
        return Response({'error': 'customer_id is required'}, status=status.HTTP_400_BAD_REQUEST)

    orders = Order.objects.filter(user_id=customer_id).order_by('-created_at')
    serializer = OrderSerializer(orders, many=True)
    return Response({'orders': serializer.data}, status=status.HTTP_200_OK)
