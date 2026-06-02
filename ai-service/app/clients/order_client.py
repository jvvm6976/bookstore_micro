"""OrderServiceClient."""
from __future__ import annotations
from .base import ServiceClient, _extract_list
from ..core.config import ORDER_SERVICE_URL


class OrderServiceClient(ServiceClient):
    def __init__(self):
        super().__init__(ORDER_SERVICE_URL, "order-service")

    def get_orders_by_customer(self, customer_id: int) -> list[dict]:
        data = self.get("/internal/orders/by_customer/", params={"customer_id": customer_id})
        if not data:
            return []
        return data.get("orders", _extract_list(data))

    def get_order_by_id(self, order_id: int) -> dict | None:
        data = self.get(f"/internal/orders/{order_id}/")
        if not data:
            return None
        return data.get("order", data)

    def get_order_detail(self, order_id: int) -> dict | None:
        return self.get_order_by_id(order_id)


order_client = OrderServiceClient()
