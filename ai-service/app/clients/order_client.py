"""OrderServiceClient.

Order-service actual endpoints:
  GET  /orders/                          — list orders of authenticated user (needs JWT)
  GET  /orders/{id}/                     — order detail
  GET  /internal/orders/{order_id}/      — internal: get order by id (no auth)
  PUT  /internal/orders/{order_id}/status/ — internal: update status

Order serializer fields:
  id, user_id, total_price, current_status, created_at, updated_at,
  items[{id, order, product_id, quantity, unit_price}],
  address{id, order, receiver_name, full_address, phone},
  status_histories[...]
"""
from __future__ import annotations
from .base import ServiceClient, _extract_list
from ..core.config import ORDER_SERVICE_URL


def _normalize_order(raw: dict) -> dict:
    """Map order-service field names to AI-service internal schema."""
    return {
        # keep original fields
        **raw,
        # aliases so downstream code can use either name
        "status":        raw.get("current_status", ""),
        "total_amount":  float(raw.get("total_price") or 0),
        # flatten address snapshot for easy access
        "shipping_address": (raw.get("address") or {}).get("full_address", ""),
    }


class OrderServiceClient(ServiceClient):
    def __init__(self):
        super().__init__(ORDER_SERVICE_URL, "order-service")

    def get_orders_by_customer(self, customer_id: int) -> list[dict]:
        """
        Fetch orders for a customer via the internal endpoint.
        The public /orders/ endpoint requires a JWT; the internal endpoint
        accepts a customer_id query param without auth.
        """
        data = self.get("/internal/orders/by_customer/", params={"customer_id": customer_id})
        if not data:
            return []
        orders = data.get("orders", _extract_list(data))
        return [_normalize_order(o) for o in orders]

    def get_order_by_id(self, order_id: int) -> dict | None:
        """Use the internal (no-auth) detail endpoint."""
        data = self.get(f"/internal/orders/{order_id}/")
        if not data:
            return None
        raw = data.get("order", data)
        return _normalize_order(raw)


order_client = OrderServiceClient()
