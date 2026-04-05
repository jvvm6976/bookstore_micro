import uuid
from datetime import timedelta
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Shipment, ShipmentStatus
from .serializers import ShipmentSerializer, ShipmentCreateSerializer, ShipmentUpdateStatusSerializer

class ShipmentViewSet(viewsets.ModelViewSet):
    """Shipping Service - Shipment creation, tracking, and management"""
    queryset = Shipment.objects.all()
    serializer_class = ShipmentSerializer

    @action(detail=False, methods=['post'])
    def create_shipment(self, request):
        """Create a shipment for an order"""
        serializer = ShipmentCreateSerializer(data=request.data)
        if serializer.is_valid():
            order_id = serializer.validated_data['order_id']
            address = serializer.validated_data['address']
            shipping_method = serializer.validated_data.get('shipping_method', 'standard')
            customer_id = serializer.validated_data.get('customer_id')
            
            # Check if shipment already exists for this order
            if Shipment.objects.filter(order_id=order_id).exists():
                return Response({'error': 'Shipment already exists for this order'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Create shipment with tracking number
            days_delta = 3 if shipping_method == 'standard' else 1
            estimated_delivery = timezone.now().date() + timedelta(days=days_delta)
            
            shipment = Shipment.objects.create(
                order_id=order_id,
                shipping_address=address,
                shipping_method=shipping_method,
                tracking_number=f"TRACK{uuid.uuid4().hex[:12].upper()}",
                status=ShipmentStatus.PROCESSING,
                estimated_delivery=estimated_delivery
            )
            
            return Response({
                'message': 'Shipment created successfully',
                'shipment': ShipmentSerializer(shipment).data
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'])
    def update_status(self, request, pk=None):
        """Update shipment status"""
        shipment = self.get_object()
        serializer = ShipmentUpdateStatusSerializer(data=request.data)
        
        if serializer.is_valid():
            new_status = serializer.validated_data['status']
            shipment.status = new_status
            
            # If delivered, set to delivered date
            if new_status == ShipmentStatus.DELIVERED:
                shipment.estimated_delivery = timezone.now().date()
            
            shipment.save()
            
            return Response({
                'message': 'Status updated successfully',
                'shipment': ShipmentSerializer(shipment).data
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def track(self, request):
        """Track a shipment by tracking number"""
        tracking_number = request.data.get('tracking_number')
        
        if not tracking_number:
            return Response({'error': 'tracking_number is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            shipment = Shipment.objects.get(tracking_number=tracking_number)
            return Response({
                'tracking_number': tracking_number,
                'shipment': ShipmentSerializer(shipment).data
            }, status=status.HTTP_200_OK)
        except Shipment.DoesNotExist:
            return Response({'error': 'Shipment not found'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['get'])
    def track_by_order(self, request):
        """Track shipment by order ID"""
        order_id = request.query_params.get('order_id')
        
        if not order_id:
            return Response({'error': 'order_id parameter is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            shipment = Shipment.objects.get(order_id=order_id)
            return Response(ShipmentSerializer(shipment).data, status=status.HTTP_200_OK)
        except Shipment.DoesNotExist:
            return Response({'error': 'No shipment found for this order'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post'])
    def ship_order(self, request):
        """Mark order as shipped"""
        shipment_id = request.data.get('shipment_id')
        
        if not shipment_id:
            return Response({'error': 'shipment_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            shipment = Shipment.objects.get(id=shipment_id)
            if shipment.status != ShipmentStatus.PROCESSING:
                return Response({'error': 'Can only ship items in processing status'}, status=status.HTTP_400_BAD_REQUEST)
            
            shipment.status = ShipmentStatus.SHIPPED
            shipment.save()
            
            return Response({
                'message': 'Order shipped successfully',
                'shipment': ShipmentSerializer(shipment).data
            }, status=status.HTTP_200_OK)
        except Shipment.DoesNotExist:
            return Response({'error': 'Shipment not found'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post'])
    def deliver_order(self, request):
        """Mark order as delivered"""
        shipment_id = request.data.get('shipment_id')
        
        if not shipment_id:
            return Response({'error': 'shipment_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            shipment = Shipment.objects.get(id=shipment_id)
            if shipment.status != ShipmentStatus.SHIPPED:
                return Response({'error': 'Can only deliver shipped items'}, status=status.HTTP_400_BAD_REQUEST)
            
            shipment.status = ShipmentStatus.DELIVERED
            shipment.save()
            
            # Update order status in Order Service
            import requests
            try:
                requests.patch(
                    f'http://order-service:8000/api/orders/{shipment.order_id}/',
                    data={'status': 'shipped'}
                )
            except:
                pass
            
            return Response({
                'message': 'Order delivered successfully',
                'shipment': ShipmentSerializer(shipment).data
            }, status=status.HTTP_200_OK)
        except Shipment.DoesNotExist:
            return Response({'error': 'Shipment not found'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['get'])
    def pending_shipments(self, request):
        """Get pending shipments"""
        shipments = Shipment.objects.filter(status=ShipmentStatus.PENDING)
        serializer = self.get_serializer(shipments, many=True)
        
        return Response({
            'count': len(shipments),
            'shipments': serializer.data
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def shipment_statistics(self, request):
        """Get shipment statistics"""
        from django.db.models import Count
        
        stats = Shipment.objects.values('status').annotate(count=Count('id'))
        
        total = sum(item['count'] for item in stats)
        
        return Response({
            'total_shipments': total,
            'by_status': {item['status']: item['count'] for item in stats}
        }, status=status.HTTP_200_OK)
        """Track shipment by order_id"""
        order_id = request.data.get('order_id')
        if not order_id:
            return Response({'error': 'order_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            shipment = Shipment.objects.get(order_id=order_id)
            return Response(ShipmentSerializer(shipment).data, status=status.HTTP_200_OK)
        except Shipment.DoesNotExist:
            return Response({'error': 'Shipment not found'}, status=status.HTTP_404_NOT_FOUND)
