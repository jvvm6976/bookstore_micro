"""UserServiceClient (customer compatibility methods)."""
from __future__ import annotations
from .base import ServiceClient, _extract_list
from ..core.config import USER_SERVICE_URL


class CustomerServiceClient(ServiceClient):
    def __init__(self):
        super().__init__(USER_SERVICE_URL, "user-service")

    def get_customer_by_id(self, customer_id: int) -> dict | None:
        return self.get(f"/internal/users/{customer_id}/")

    def get_customer_history(self, customer_id: int) -> dict:
        """Returns cart + profile info for a customer."""
        data = self.get(f"/internal/users/{customer_id}/")
        if not data:
            return {}
        return data


customer_client = CustomerServiceClient()
