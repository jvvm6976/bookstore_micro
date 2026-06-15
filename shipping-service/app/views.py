import logging
import os
import requests
from rest_framework import viewsets, generics, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from .models import Shipment, ShipmentTracking
from .serializers import ShipmentSerializer, ShipmentTrackingSerializer

logger = logging.getLogger(__name__)

ORDER_SERVICE_URL = os.environ.get('ORDER_SERVICE_URL', 'http://order-service:8000')
PAYMENT_SERVICE_URL = os.environ.get('PAYMENT_SERVICE_URL', 'http://payment-service:8000')
NOTIFICATION_SERVICE_URL = os.environ.get('NOTIFICATION_SERVICE_URL', 'http://notification-service:8000')
SHIPPING_STATUS_LABELS = {
    'processing': 'đang chuẩn bị',
    'shipping': 'đang giao',
    'delivered': 'đã giao',
    'cancelled': 'đã hủy',
}


def _shipping_status_label(value):
    return SHIPPING_STATUS_LABELS.get(value, value or 'chưa xác định')


def _send_notification(payload):
    try:
        requests.post(
            f"{NOTIFICATION_SERVICE_URL}/internal/notifications/",
            json=payload,
            timeout=5
        )
    except Exception as e:
        logger.warning(f"Warning: Failed to send notification: {str(e)}")


def _notify_customer(user_id, title, content, order_id, priority='normal'):
    _send_notification({
        'user_id': user_id,
        'recipient_type': 'customer',
        'title': title,
        'content': content,
        'type': 'shipping',
        'entity_type': 'order',
        'entity_id': order_id,
        'priority': priority,
        'status': 'unread',
    })


def _notify_staff(title, content, order_id, priority='normal'):
    _send_notification({
        'recipient_type': 'staff',
        'title': title,
        'content': content,
        'type': 'shipping',
        'entity_type': 'order',
        'entity_id': order_id,
        'priority': priority,
        'status': 'unread',
    })


def _get_order_or_error(order_id):
    try:
        order_resp = requests.get(f"{ORDER_SERVICE_URL}/internal/orders/{order_id}/", timeout=5)
    except requests.RequestException as exc:
        logger.error("Error calling order service: %s", exc)
        raise ValidationError({'error': 'Failed to validate order'})

    if order_resp.status_code != 200:
        raise ValidationError({'error': 'Order not found'})
    return order_resp.json()


def _is_staff_user(user):
    return getattr(user, 'role', None) in {'admin', 'manager', 'staff'}


def _assert_can_view_order(user, order_id):
    if _is_staff_user(user):
        return _get_order_or_error(order_id)
    order_data = _get_order_or_error(order_id)
    if int(order_data.get('user_id') or 0) != int(user.id):
        raise PermissionDenied('You can only view shipments for your own orders')
    return order_data


def _assert_staff(user):
    if not _is_staff_user(user):
        raise PermissionDenied('Only staff can update shipment operations')


class ShipmentListView(generics.ListAPIView):
    """
    Get all shipments
    GET /shipping/
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = ShipmentSerializer
    def get_queryset(self):
        if _is_staff_user(self.request.user):
            return Shipment.objects.all().order_by('-created_at')

        try:
            orders_resp = requests.get(
                f"{ORDER_SERVICE_URL}/internal/orders/by_customer/",
                params={'customer_id': self.request.user.id},
                timeout=5
            )
            if orders_resp.status_code != 200:
                return Shipment.objects.none()
            order_ids = [
                row.get('id')
                for row in orders_resp.json().get('orders', [])
                if row.get('id') is not None
            ]
            return Shipment.objects.filter(order_id__in=order_ids).order_by('-created_at')
        except requests.RequestException:
            return Shipment.objects.none()


class ShipmentDetailView(generics.RetrieveAPIView):
    """
    Get shipment by order_id
    GET /shipping/{order_id}/
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = ShipmentSerializer
    
    def get_object(self):
        order_id = self.kwargs.get('pk')
        _assert_can_view_order(self.request.user, order_id)
        try:
            return Shipment.objects.get(order_id=order_id)
        except Shipment.DoesNotExist:
            raise ValidationError({'error': 'Shipment not found'})


class ShipmentTrackingListView(generics.ListAPIView):
    """
    Get tracking history by order_id
    GET /shipping/tracking/{order_id}/
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = ShipmentTrackingSerializer
    
    def get_queryset(self):
        order_id = self.kwargs.get('pk')
        try:
            _assert_can_view_order(self.request.user, order_id)
            shipment = Shipment.objects.get(order_id=order_id)
            return ShipmentTracking.objects.filter(shipment=shipment).order_by('-updated_at')
        except Shipment.DoesNotExist:
            return ShipmentTracking.objects.none()


class ShipmentStatusUpdateView(generics.UpdateAPIView):
    """
    Update shipment status (admin/staff only)
    PUT /shipping/{order_id}/status/
    
    Request: {current_status} (processing, shipping, delivered)
    Response: {id, order_id, receiver_name, phone, full_address, current_status}
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = ShipmentSerializer
    
    def get_object(self):
        order_id = self.kwargs.get('pk')
        _assert_staff(self.request.user)
        try:
            return Shipment.objects.get(order_id=order_id)
        except Shipment.DoesNotExist:
            raise ValidationError({'error': 'Shipment not found'})
    
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        shipment = self.get_object()
        new_status = request.data.get('current_status')
        
        if not new_status:
            raise ValidationError({'error': 'current_status is required'})
        
        if new_status not in ['processing', 'shipping', 'delivered']:
            raise ValidationError({'error': 'Invalid current_status'})
        
        # Validate state transitions
        valid_transitions = {
            'processing': ['shipping'],
            'shipping': ['delivered'],
            'delivered': []
        }
        
        if new_status not in valid_transitions.get(shipment.current_status, []):
            raise ValidationError({
                'error': f'Cannot transition from {shipment.current_status} to {new_status}'
            })
        
        shipment.current_status = new_status
        shipment.save()
        
        # Add tracking entry
        ShipmentTracking.objects.create(
            shipment=shipment,
            status=new_status,
            location=request.data.get('location', '')
        )
        
        # A COD payment is only collected after delivery succeeds.
        if new_status == 'delivered':
            try:
                payment_resp = requests.post(
                    f"{PAYMENT_SERVICE_URL}/internal/payments/{shipment.order_id}/collect-cod/",
                    timeout=5,
                )
                if payment_resp.status_code >= 400:
                    raise ValidationError({'error': 'Failed to collect COD payment'})
            except ValidationError:
                raise
            except requests.RequestException as exc:
                logger.warning("Failed to collect COD payment for order %s: %s", shipment.order_id, exc)
                raise ValidationError({'error': 'Failed to collect COD payment'})

        # Keep order status in sync with shipping progress.
        order_data = _get_order_or_error(shipment.order_id)
        order_status = 'completed' if new_status == 'delivered' else new_status
        try:
            status_resp = requests.put(
                f"{ORDER_SERVICE_URL}/internal/orders/{shipment.order_id}/status/",
                json={'status': order_status},
                timeout=5
            )
            if status_resp.status_code >= 400:
                raise ValidationError({'error': 'Failed to update order status'})
        except ValidationError:
            raise
        except Exception as e:
            logger.warning(f"Warning: Failed to update order status: {str(e)}")
            raise ValidationError({'error': 'Failed to update order status'})

        if new_status == 'shipping':
            _notify_customer(
                order_data.get('user_id'),
                'Đơn hàng đang được giao',
                f'Đơn hàng #{shipment.order_id} đã rời kho và đang trên đường giao tới bạn.',
                shipment.order_id,
            )
        elif new_status == 'delivered':
            _notify_customer(
                order_data.get('user_id'),
                'Đơn hàng đã giao',
                f'Đơn hàng #{shipment.order_id} đã được giao thành công. Bạn có thể đánh giá sản phẩm trong mục Đơn hàng.',
                shipment.order_id,
                priority='high',
            )
            _notify_staff(
                'Vận đơn đã hoàn tất',
                f'Vận đơn của đơn hàng #{shipment.order_id} đã hoàn tất giao hàng.',
                shipment.order_id,
            )
        
        serializer = self.get_serializer(shipment)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ShipmentTrackingAddView(generics.CreateAPIView):
    """
    Add tracking entry
    POST /shipping/{order_id}/tracking/
    
    Request: {location, status}
    Response: {id, shipment_id, location, status, updated_at}
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = ShipmentTrackingSerializer
    
    def create(self, request, *args, **kwargs):
        _assert_staff(request.user)
        order_id = self.kwargs.get('pk')
        location = request.data.get('location')
        status_val = request.data.get('status')
        
        if not status_val:
            raise ValidationError({'error': 'status is required'})
        
        try:
            shipment = Shipment.objects.get(order_id=order_id)
        except Shipment.DoesNotExist:
            raise ValidationError({'error': 'Shipment not found'})
        
        tracking = ShipmentTracking.objects.create(
            shipment=shipment,
            location=location or '',
            status=status_val
        )
        
        serializer = ShipmentTrackingSerializer(tracking)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ShipmentDeleteView(generics.DestroyAPIView):
    """
    Delete/Cancel shipment (only if not shipped)
    DELETE /shipping/{order_id}/
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = ShipmentSerializer
    
    def get_object(self):
        order_id = self.kwargs.get('pk')
        _assert_staff(self.request.user)
        try:
            return Shipment.objects.get(order_id=order_id)
        except Shipment.DoesNotExist:
            raise ValidationError({'error': 'Shipment not found'})
    
    def destroy(self, request, *args, **kwargs):
        shipment = self.get_object()
        
        # Only allow delete if status is processing
        if shipment.current_status != 'processing':
            raise ValidationError({
                'error': f'Cannot delete shipment in {shipment.current_status} status'
            })
        
        shipment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# Internal APIs

class InternalShipmentCreateView(generics.CreateAPIView):
    """
    Internal API - Create shipment (called from Order Service)
    POST /internal/shipments/
    
    Request: {order_id, receiver_name, phone, full_address}
    Response: {id, order_id, receiver_name, phone, full_address, current_status}
    """
    permission_classes = (AllowAny,)
    serializer_class = ShipmentSerializer
    
    def create(self, request, *args, **kwargs):
        order_id = request.data.get('order_id')
        receiver_name = request.data.get('receiver_name')
        phone = request.data.get('phone')
        full_address = request.data.get('full_address')
        
        # Validation
        if not all([order_id, receiver_name, phone, full_address]):
            raise ValidationError({'error': 'order_id, receiver_name, phone, full_address are required'})
        
        # Check if shipment already exists
        if Shipment.objects.filter(order_id=order_id).exists():
            raise ValidationError({'error': 'Shipment already exists for this order'})
        
        try:
            shipment = Shipment.objects.create(
                order_id=order_id,
                receiver_name=receiver_name,
                phone=phone,
                full_address=full_address,
                current_status=Shipment.STATUS_PROCESSING
            )
            
            # Add initial tracking entry
            ShipmentTracking.objects.create(
                shipment=shipment,
                status=Shipment.STATUS_PROCESSING,
                location='Kho ShopSphere'
            )

            _notify_staff(
                'Vận đơn mới cần xử lý',
                f'Đơn hàng #{order_id} đã có vận đơn mới cho {receiver_name}. Kiểm tra địa chỉ và chuẩn bị giao hàng.',
                order_id,
                priority='high',
            )
            
            serializer = ShipmentSerializer(shipment)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error creating shipment: {str(e)}")
            return Response(
                {'error': f'Failed to create shipment: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class InternalShipmentCancelView(generics.GenericAPIView):
    """
    Internal API - Cancel shipment when the owning order is cancelled.
    POST /internal/shipments/{order_id}/cancel/
    """
    permission_classes = (AllowAny,)

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        order_id = self.kwargs.get('order_id')

        try:
            shipment = Shipment.objects.get(order_id=order_id)
        except Shipment.DoesNotExist:
            return Response({'error': 'Shipment not found'}, status=status.HTTP_404_NOT_FOUND)

        if shipment.current_status == 'delivered':
            raise ValidationError({'error': 'Delivered shipment cannot be cancelled'})

        if shipment.current_status != 'cancelled':
            previous_status = shipment.current_status
            shipment.current_status = 'cancelled'
            shipment.save()
            ShipmentTracking.objects.create(
                shipment=shipment,
                status='cancelled',
                location=request.data.get('location', 'Order cancelled')
            )
            _notify_staff(
                'Vận đơn đã hủy',
                f'Vận đơn của đơn hàng #{order_id} đã được hủy khi đang {_shipping_status_label(previous_status)}.',
                order_id,
                priority='high',
            )

        serializer = ShipmentSerializer(shipment)
        return Response(serializer.data, status=status.HTTP_200_OK)
