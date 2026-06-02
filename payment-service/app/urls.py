from django.urls import path
from .views import (
    PaymentProcessView,
    PaymentDetailView,
    PaymentTransactionListView,
    PaymentStatusUpdateView,
    InternalPaymentCreateView,
    InternalPaymentRefundView
)

urlpatterns = [
    # Client APIs
    path('payment/pay/', PaymentProcessView.as_view(), name='payment-pay'),
    path('payments/<int:pk>/', PaymentDetailView.as_view(), name='payment-detail'),
    path('payments/<int:pk>/transactions/', PaymentTransactionListView.as_view(), name='payment-transactions'),
    path('payments/<int:pk>/status/', PaymentStatusUpdateView.as_view(), name='payment-status-update'),
    
    # Internal APIs
    path('internal/payments/', InternalPaymentCreateView.as_view(), name='internal-payment-create'),
    path('internal/payments/<int:order_id>/refund/', InternalPaymentRefundView.as_view(), name='internal-payment-refund'),
]
