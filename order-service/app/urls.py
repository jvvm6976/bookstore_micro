from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    OrderViewSet,
    OrderCheckoutView,
    internal_orders_by_customer,
    internal_order_status_update,
    internal_order_detail,
)

router = DefaultRouter()
router.register(r'orders', OrderViewSet, basename='order')

urlpatterns = [
    path('orders/checkout/', OrderCheckoutView.as_view(), name='order_checkout'),
    path('internal/orders/by_customer/', internal_orders_by_customer, name='internal-orders-by-customer'),
    path('internal/orders/<int:order_id>/', internal_order_detail, name='internal-order-detail'),
    path('internal/orders/<int:order_id>/status/', internal_order_status_update, name='internal-order-status-update'),
    path('', include(router.urls)),
]
