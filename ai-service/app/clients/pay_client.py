"""PayServiceClient.

Payment-service actual endpoints:
  GET  /payments/<order_id>/            — payment detail by order_id
  GET  /payments/<order_id>/transactions/ — transactions by order_id

Payment serializer fields (PaymentSerializer):
  id, order_id, amount, payment_method, overall_status, created_at, updated_at
"""
from __future__ import annotations
from .base import ServiceClient
from ..core.config import PAY_SERVICE_URL


class PayServiceClient(ServiceClient):
    def __init__(self):
        super().__init__(PAY_SERVICE_URL, "payment-service")

    def get_payment_status(self, order_id: int) -> dict | None:
        """
        GET /payments/<order_id>/ — payment-service uses order_id as the PK lookup.
        Returns normalized dict with 'status' and 'payment_method' keys.
        """
        data = self.get(f"/payments/{order_id}/")
        if not data:
            return None
        return {
            **data,
            # normalize field name: overall_status → status
            "status":         data.get("overall_status", ""),
            "payment_method": data.get("payment_method", ""),
        }


pay_client = PayServiceClient()
