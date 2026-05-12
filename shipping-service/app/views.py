import logging
import requests
from rest_framework import viewsets, generics, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import ValidationError
from django.db import transaction
from .models import Shipment, ShipmentTracking
from .serializers import ShipmentSerializer, ShipmentTrackingSerializer

logger = logging.getLogger(__name__)

ORDER_SERVICE_URL = 'http://order-service:8000'
NOTIFICATION_SERVICE_URL = 'http://notification-service:8000'


class ShipmentListView(generics.ListAPIView):
    """
    Get all shipments
    GET /shipping/
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = ShipmentSerializer
    queryset = Shipment.objects.all().order_by('-created_at')


class ShipmentDetailView(generics.RetrieveAPIView):
    """
    Get shipment by order_id
    GET /shipping/{order_id}/
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = ShipmentSerializer
    
    def get_object(self):
        order_id = self.kwargs.get('pk')
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
        
        # Update order status if delivered
        if new_status == 'delivered':
            try:
                requests.put(
                    f"{ORDER_SERVICE_URL}/internal/orders/{shipment.order_id}/status/",
                    json={'status': 'completed'},
                    timeout=5
                )
            except Exception as e:
                logger.warning(f"Warning: Failed to update order status: {str(e)}")
            
            # Send notification
            try:
                requests.post(
                    f"{NOTIFICATION_SERVICE_URL}/internal/notifications/",
                    json={
                        'user_id': request.user.id,
                        'title': 'Đơn hàng đã giao',
                        'content': f'Đơn hàng #{shipment.order_id} đã được giao thành công',
                        'type': 'shipping',
                        'status': 'unread'
                    },
                    timeout=5
                )
            except Exception as e:
                logger.warning(f"Warning: Failed to send notification: {str(e)}")
        
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
                location='Warehouse'
            )
            
            serializer = ShipmentSerializer(shipment)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error creating shipment: {str(e)}")
            return Response(
                {'error': f'Failed to create shipment: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
