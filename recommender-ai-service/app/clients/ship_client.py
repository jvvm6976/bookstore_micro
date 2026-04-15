"""ShipServiceClient."""
from __future__ import annotations
from .base import ServiceClient
from ..core.config import SHIP_SERVICE_URL


class ShipServiceClient(ServiceClient):
    def __init__(self):
        super().__init__(SHIP_SERVICE_URL, "ship-service")

    def get_shipping_status(self, order_id: int) -> dict | None:
        return self.get("/api/shipments/track_by_order/", params={"order_id": order_id})


ship_client = ShipServiceClient()
