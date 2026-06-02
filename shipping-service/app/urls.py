from django.urls import path
from .views import (
    ShipmentListView,
    ShipmentDetailView,
    ShipmentTrackingListView,
    ShipmentStatusUpdateView,
    ShipmentTrackingAddView,
    ShipmentDeleteView,
    InternalShipmentCreateView,
    InternalShipmentCancelView
)

urlpatterns = [
    # Internal APIs (must be first to avoid conflicts)
    path('internal/shipments/', InternalShipmentCreateView.as_view(), name='internal-shipment-create'),
    path('internal/shipments/<int:order_id>/cancel/', InternalShipmentCancelView.as_view(), name='internal-shipment-cancel'),
    
    # Client APIs - More specific paths first
    path('shipping/tracking/<int:pk>/', ShipmentTrackingListView.as_view(), name='shipment-tracking-list'),
    path('shipping/<int:pk>/status/', ShipmentStatusUpdateView.as_view(), name='shipment-status-update'),
    path('shipping/<int:pk>/tracking/', ShipmentTrackingAddView.as_view(), name='shipment-tracking-add'),
    path('shipping/<int:pk>/delete/', ShipmentDeleteView.as_view(), name='shipment-delete'),
    path('shipping/<int:pk>/', ShipmentDetailView.as_view(), name='shipment-detail'),
    path('shipping/', ShipmentListView.as_view(), name='shipment-list'),
]
