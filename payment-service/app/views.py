import uuid
import os
import requests
import logging
from decimal import Decimal, InvalidOperation
from rest_framework import viewsets, generics, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from .models import Payment, PaymentTransaction
from .serializers import PaymentSerializer, PaymentTransactionSerializer

logger = logging.getLogger(__name__)

ORDER_SERVICE_URL = os.environ.get('ORDER_SERVICE_URL', 'http://order-service:8000')
NOTIFICATION_SERVICE_URL = os.environ.get('NOTIFICATION_SERVICE_URL', 'http://notification-service:8000')
PAYMENT_METHOD_LABELS = {
    'cod': 'thanh toán khi nhận hàng',
    'vnpay': 'VNPAY',
    'momo': 'MoMo',
    'stripe': 'thẻ quốc tế',
}


def _format_money(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        amount = Decimal('0')
    return f"{amount:,.0f}".replace(',', '.') + 'đ'


def _payment_method_label(value):
    return PAYMENT_METHOD_LABELS.get(str(value or '').lower(), value or 'phương thức đã chọn')


def _send_notification(payload):
    try:
        requests.post(
            f"{NOTIFICATION_SERVICE_URL}/internal/notifications/",
            json=payload,
            timeout=5
        )
    except Exception as e:
        logger.warning(f"Warning: Failed to send notification: {str(e)}")


def _notify_customer(user_id, title, content, notif_type, order_id, priority='normal'):
    _send_notification({
        'user_id': user_id,
        'recipient_type': 'customer',
        'title': title,
        'content': content,
        'type': notif_type,
        'entity_type': 'order',
        'entity_id': order_id,
        'priority': priority,
        'status': 'unread',
    })


def _notify_staff(title, content, notif_type, order_id, priority='normal'):
    _send_notification({
        'recipient_type': 'staff',
        'title': title,
        'content': content,
        'type': notif_type,
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


def _validate_order_owner(order_data, user_id):
    if int(order_data.get('user_id') or 0) != int(user_id):
        raise ValidationError({'error': 'You can only access your own order payment'})


def _is_staff_user(user):
    return getattr(user, 'role', None) in {'admin', 'manager', 'staff'}


def _validate_payment_access(order_data, user):
    if _is_staff_user(user):
        return
    _validate_order_owner(order_data, user.id)


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
            amount = Decimal(str(amount))
            if amount <= 0:
                raise ValidationError({'error': 'Amount must be greater than 0'})
        except (InvalidOperation, ValueError, TypeError):
            raise ValidationError({'error': 'Invalid amount'})
        
        if payment_method not in ['vnpay', 'momo', 'cod', 'stripe']:
            raise ValidationError({'error': 'Invalid payment_method'})
        
        # Check if payment already exists for this order
        if Payment.objects.filter(order_id=order_id).exists():
            raise ValidationError({'error': 'Payment already exists for this order'})

        order_data = _get_order_or_error(order_id)
        _validate_order_owner(order_data, request.user.id)
        order_status = order_data.get('current_status')
        if order_status != 'pending':
            raise ValidationError({'error': f'Order cannot be paid in {order_status} status'})

        expected_amount = Decimal(str(order_data.get('total_price') or 0))
        if amount != expected_amount:
            raise ValidationError({'error': 'Payment amount does not match order total'})
        
        try:
            # Create payment record
            payment = Payment.objects.create(
                order_id=order_id,
                amount=amount,
                payment_method=payment_method,
                overall_status=Payment.STATUS_PENDING
            )
            
            is_cod = payment_method == 'cod'
            payment.overall_status = (
                Payment.STATUS_PENDING if is_cod else Payment.STATUS_SUCCESS
            )
            payment.save()
            
            # Log transaction
            PaymentTransaction.objects.create(
                payment=payment,
                transaction_note=(
                    'Đăng ký thanh toán khi nhận hàng'
                    if is_cod
                    else f'Thanh toán qua {_payment_method_label(payment_method)}'
                ),
                transaction_code=str(uuid.uuid4())
            )
            
            # Update order status to 'paid'
            try:
                status_resp = requests.put(
                    f"{ORDER_SERVICE_URL}/internal/orders/{order_id}/status/",
                    json={'status': 'paid'},
                    timeout=5
                )
                if status_resp.status_code >= 400:
                    raise ValidationError({'error': 'Failed to update order status'})
            except ValidationError:
                raise
            except Exception as e:
                logger.warning(f"Warning: Failed to update order status: {str(e)}")
                raise ValidationError({'error': 'Failed to update order status'})
            
            if is_cod:
                _notify_customer(
                    request.user.id,
                    'Đơn hàng đã được xác nhận',
                    f'Đơn hàng #{order_id} sẽ thu {_format_money(amount)} khi giao hàng. Bạn chưa bị trừ tiền.',
                    'payment',
                    order_id,
                )
                _notify_staff(
                    'Đơn COD mới',
                    f'Đơn hàng #{order_id} đã chọn thanh toán khi nhận hàng, số tiền cần thu là {_format_money(amount)}.',
                    'payment',
                    order_id,
                    priority='high',
                )
            else:
                _notify_customer(
                    request.user.id,
                    'Thanh toán thành công',
                    f'ShopSphere đã xác nhận thanh toán {_format_money(amount)} cho đơn hàng #{order_id}.',
                    'payment',
                    order_id,
                )
                _notify_staff(
                    'Đơn hàng đã thanh toán',
                    f'Đơn hàng #{order_id} đã thanh toán {_format_money(amount)} qua {_payment_method_label(payment_method)}.',
                    'payment',
                    order_id,
                    priority='high',
                )
            
            serializer = PaymentSerializer(payment)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except ValidationError:
            raise
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
            payment = Payment.objects.get(order_id=order_id)
        except Payment.DoesNotExist:
            raise ValidationError({'error': 'Payment not found'})
        order_data = _get_order_or_error(order_id)
        _validate_payment_access(order_data, self.request.user)
        return payment


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
            order_data = _get_order_or_error(order_id)
            _validate_payment_access(order_data, self.request.user)
            payment = Payment.objects.get(order_id=order_id)
            return PaymentTransaction.objects.filter(payment=payment).order_by('-created_at')
        except (Payment.DoesNotExist, ValidationError):
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
        if not _is_staff_user(request.user):
            raise PermissionDenied('Only staff can update payment status')
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


class InternalPaymentRefundView(generics.GenericAPIView):
    """
    Internal API - Mark payment as refunded when an order is cancelled.
    POST /internal/payments/{order_id}/refund/
    """
    permission_classes = (AllowAny,)

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        order_id = self.kwargs.get('order_id')
        reason = request.data.get('reason', 'Order cancelled')

        try:
            payment = Payment.objects.get(order_id=order_id)
        except Payment.DoesNotExist:
            return Response({'error': 'Payment not found'}, status=status.HTTP_404_NOT_FOUND)

        if payment.overall_status == Payment.STATUS_REFUNDED:
            serializer = PaymentSerializer(payment)
            return Response(serializer.data, status=status.HTTP_200_OK)

        if payment.overall_status not in [Payment.STATUS_PENDING, Payment.STATUS_SUCCESS]:
            raise ValidationError({'error': f'Payment cannot be refunded in {payment.overall_status} status'})

        is_uncollected_cod = (
            payment.payment_method == 'cod'
            and payment.overall_status == Payment.STATUS_PENDING
        )
        payment.overall_status = (
            Payment.STATUS_FAILED if is_uncollected_cod else Payment.STATUS_REFUNDED
        )
        payment.save()
        PaymentTransaction.objects.create(
            payment=payment,
            transaction_note=(
                f'Hủy thanh toán khi nhận hàng: {reason}'
                if is_uncollected_cod
                else f'Hoàn tiền: {reason}'
            ),
            transaction_code=str(uuid.uuid4())
        )

        serializer = PaymentSerializer(payment)
        return Response(serializer.data, status=status.HTTP_200_OK)


class InternalCodCollectionView(generics.GenericAPIView):
    """
    Internal API - Collect a pending COD payment after successful delivery.
    POST /internal/payments/{order_id}/collect-cod/
    """
    permission_classes = (AllowAny,)

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        order_id = self.kwargs.get('order_id')
        try:
            payment = Payment.objects.get(order_id=order_id)
        except Payment.DoesNotExist:
            return Response({'error': 'Payment not found'}, status=status.HTTP_404_NOT_FOUND)

        if payment.payment_method != 'cod':
            return Response({
                'collected': False,
                'reason': 'Payment method is not COD',
                'payment': PaymentSerializer(payment).data,
            }, status=status.HTTP_200_OK)

        if payment.overall_status == Payment.STATUS_SUCCESS:
            return Response({
                'collected': True,
                'payment': PaymentSerializer(payment).data,
            }, status=status.HTTP_200_OK)

        if payment.overall_status != Payment.STATUS_PENDING:
            raise ValidationError({
                'error': f'COD payment cannot be collected in {payment.overall_status} status'
            })

        order_data = _get_order_or_error(order_id)
        payment.overall_status = Payment.STATUS_SUCCESS
        payment.save(update_fields=['overall_status', 'updated_at'])
        PaymentTransaction.objects.create(
            payment=payment,
            transaction_note='Đã thu tiền COD khi giao hàng',
            transaction_code=str(uuid.uuid4()),
        )

        _notify_customer(
            order_data.get('user_id'),
            'Đã thanh toán khi nhận hàng',
            f'ShopSphere đã ghi nhận {_format_money(payment.amount)} của đơn hàng #{order_id} sau khi giao thành công.',
            'payment',
            order_id,
        )
        _notify_staff(
            'Đã thu tiền COD',
            f'Đơn hàng #{order_id} đã thu đủ {_format_money(payment.amount)} khi giao hàng.',
            'payment',
            order_id,
        )

        return Response({
            'collected': True,
            'payment': PaymentSerializer(payment).data,
        }, status=status.HTTP_200_OK)
