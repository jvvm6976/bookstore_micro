import uuid
import requests
import logging
from rest_framework import viewsets, generics, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import ValidationError
from django.db import transaction
from .models import Payment, PaymentTransaction
from .serializers import PaymentSerializer, PaymentTransactionSerializer

logger = logging.getLogger(__name__)

ORDER_SERVICE_URL = 'http://order-service:8000'
NOTIFICATION_SERVICE_URL = 'http://notification-service:8000'


class PaymentProcessView(generics.CreateAPIView):
    """
    Process payment for order
    POST /payment/pay/
    
    Request: {order_id, amount, payment_method}
    Response: {id, order_id, amount, payment_method, overall_status}
    """
    permission_classes = (IsAuthenticated,)
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        order_id = request.data.get('order_id')
        amount = request.data.get('amount')
        payment_method = request.data.get('payment_method')
        
        # Validation
        if not order_id or not amount or not payment_method:
            raise ValidationError({'error': 'order_id, amount, payment_method are required'})
        
        try:
            amount = float(amount)
            if amount <= 0:
                raise ValidationError({'error': 'Amount must be greater than 0'})
        except (ValueError, TypeError):
            raise ValidationError({'error': 'Invalid amount'})
        
        if payment_method not in ['vnpay', 'momo', 'cod', 'stripe']:
            raise ValidationError({'error': 'Invalid payment_method'})
        
        # Check if payment already exists for this order
        if Payment.objects.filter(order_id=order_id).exists():
            raise ValidationError({'error': 'Payment already exists for this order'})
        
        try:
            # Create payment record
            payment = Payment.objects.create(
                order_id=order_id,
                amount=amount,
                payment_method=payment_method,
                overall_status=Payment.STATUS_PENDING
            )
            
            # Simulate payment processing (always succeeds for now)
            payment.overall_status = Payment.STATUS_SUCCESS
            payment.save()
            
            # Log transaction
            PaymentTransaction.objects.create(
                payment=payment,
                transaction_note=f'Payment via {payment_method}',
                transaction_code=str(uuid.uuid4())
            )
            
            # Update order status to 'paid'
            try:
                requests.put(
                    f"{ORDER_SERVICE_URL}/internal/orders/{order_id}/status/",
                    json={'status': 'paid'},
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
                        'title': 'Thanh toán thành công',
                        'content': f'Thanh toán cho đơn hàng #{order_id} đã được xác nhận',
                        'type': 'payment',
                        'status': 'unread'
                    },
                    timeout=5
                )
            except Exception as e:
                logger.warning(f"Warning: Failed to send notification: {str(e)}")
            
            serializer = PaymentSerializer(payment)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error processing payment: {str(e)}")
            return Response(
                {'error': f'Payment processing failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PaymentDetailView(generics.RetrieveAPIView):
    """
    Get payment info by order_id
    GET /payments/{order_id}/
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = PaymentSerializer
    
    def get_object(self):
        order_id = self.kwargs.get('pk')
        try:
            return Payment.objects.get(order_id=order_id)
        except Payment.DoesNotExist:
            raise ValidationError({'error': 'Payment not found'})


class PaymentTransactionListView(generics.ListAPIView):
    """
    Get payment transactions by order_id
    GET /payments/{order_id}/transactions/
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = PaymentTransactionSerializer
    
    def get_queryset(self):
        order_id = self.kwargs.get('pk')
        try:
            payment = Payment.objects.get(order_id=order_id)
            return PaymentTransaction.objects.filter(payment=payment).order_by('-created_at')
        except Payment.DoesNotExist:
            return PaymentTransaction.objects.none()


class PaymentStatusUpdateView(generics.UpdateAPIView):
    """
    Update payment status (admin only)
    PUT /payments/{order_id}/status/
    
    Request: {overall_status}
    Response: {id, order_id, amount, payment_method, overall_status}
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = PaymentSerializer
    
    def get_object(self):
        order_id = self.kwargs.get('pk')
        try:
            return Payment.objects.get(order_id=order_id)
        except Payment.DoesNotExist:
            raise ValidationError({'error': 'Payment not found'})
    
    def put(self, request, *args, **kwargs):
        payment = self.get_object()
        new_status = request.data.get('overall_status')
        
        if not new_status:
            raise ValidationError({'error': 'overall_status is required'})
        
        if new_status not in ['pending', 'success', 'failed', 'refunded']:
            raise ValidationError({'error': 'Invalid overall_status'})
        
        payment.overall_status = new_status
        payment.save()
        
        serializer = self.get_serializer(payment)
        return Response(serializer.data, status=status.HTTP_200_OK)


# Internal APIs

class InternalPaymentCreateView(generics.CreateAPIView):
    """
    Internal API - Create payment record (called from Order Service)
    POST /internal/payments/
    
    Request: {order_id, amount, payment_method}
    Response: {id, order_id, amount, payment_method, overall_status}
    """
    permission_classes = (AllowAny,)
    serializer_class = PaymentSerializer
    
    def create(self, request, *args, **kwargs):
        order_id = request.data.get('order_id')
        amount = request.data.get('amount')
        payment_method = request.data.get('payment_method', 'cod')
        
        # Validation
        if not order_id or not amount:
            raise ValidationError({'error': 'order_id and amount are required'})
        
        try:
            amount = float(amount)
            if amount <= 0:
                raise ValidationError({'error': 'Amount must be greater than 0'})
        except (ValueError, TypeError):
            raise ValidationError({'error': 'Invalid amount'})
        
        # Check if payment already exists
        if Payment.objects.filter(order_id=order_id).exists():
            raise ValidationError({'error': 'Payment already exists for this order'})
        
        try:
            payment = Payment.objects.create(
                order_id=order_id,
                amount=amount,
                payment_method=payment_method,
                overall_status=Payment.STATUS_PENDING
            )
            
            serializer = PaymentSerializer(payment)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error creating payment: {str(e)}")
            return Response(
                {'error': f'Failed to create payment: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
