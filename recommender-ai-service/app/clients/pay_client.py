"""PayServiceClient."""
from __future__ import annotations
from .base import ServiceClient
from ..core.config import PAY_SERVICE_URL


class PayServiceClient(ServiceClient):
    def __init__(self):
        super().__init__(PAY_SERVICE_URL, "pay-service")

    def get_payment_status(self, order_id: int) -> dict | None:
        return self.get("/api/payments/by_order/", params={"order_id": order_id})


pay_client = PayServiceClient()
