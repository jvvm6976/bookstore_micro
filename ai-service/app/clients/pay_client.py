"""PayServiceClient."""
from __future__ import annotations
from .base import ServiceClient
from ..core.config import PAY_SERVICE_URL


class PayServiceClient(ServiceClient):
    def __init__(self):
        super().__init__(PAY_SERVICE_URL, "payment-service")

    def get_payment_status(self, order_id: int) -> dict | None:
        return self.get(f"/payments/{order_id}/")


pay_client = PayServiceClient()
