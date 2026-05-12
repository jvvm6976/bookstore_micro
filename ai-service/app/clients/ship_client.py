"""ShipServiceClient.

Shipping-service actual endpoints:
  GET  /shipping/<order_id>/            — shipment detail by order_id
  GET  /shipping/tracking/<order_id>/   — tracking history by order_id

Shipment serializer fields (ShipmentSerializer):
  id, order_id, receiver_name, phone, full_address, current_status,
  created_at, updated_at
"""
from __future__ import annotations
from .base import ServiceClient
from ..core.config import SHIP_SERVICE_URL


class ShipServiceClient(ServiceClient):
    def __init__(self):
        super().__init__(SHIP_SERVICE_URL, "shipping-service")

    def get_shipping_status(self, order_id: int) -> dict | None:
        """
        GET /shipping/<order_id>/ — shipping-service uses order_id as the PK lookup.
        Returns normalized dict with 'status' and 'tracking_number' keys.
        """
        data = self.get(f"/shipping/{order_id}/")
        if not data:
            return None
        # Fetch latest tracking entry for tracking_number / location
        tracking_data = self.get(f"/shipping/tracking/{order_id}/")
        tracking_list = tracking_data if isinstance(tracking_data, list) else []
        latest_tracking = tracking_list[0] if tracking_list else {}
        return {
            **data,
            # normalize field name: current_status → status
            "status":            data.get("current_status", ""),
            "tracking_number":   latest_tracking.get("location", "Chưa có"),
            "estimated_delivery": "",   # shipping-service has no ETA field yet
        }


ship_client = ShipServiceClient()
