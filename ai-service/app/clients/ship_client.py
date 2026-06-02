"""ShipServiceClient."""
from __future__ import annotations
from .base import ServiceClient
from ..core.config import SHIP_SERVICE_URL


class ShipServiceClient(ServiceClient):
    def __init__(self):
        super().__init__(SHIP_SERVICE_URL, "shipping-service")

    def get_shipping_status(self, order_id: int) -> dict | None:
        return self.get(f"/shipping/{order_id}/")

    def get_shipment_by_order(self, order_id: int) -> dict | None:
        return self.get_shipping_status(order_id)


ship_client = ShipServiceClient()
