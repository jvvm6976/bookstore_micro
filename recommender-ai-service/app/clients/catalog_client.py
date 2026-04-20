"""CatalogServiceClient — proxies to product-service books endpoints."""
from __future__ import annotations
from .base import ServiceClient, _extract_list
from ..core.config import PRODUCT_SERVICE_URL


class CatalogServiceClient(ServiceClient):
    def __init__(self):
        super().__init__(PRODUCT_SERVICE_URL, "catalog/product-service")

    def get_all_products(self, limit: int = 200) -> list[dict]:
        data = self.get("/api/books/", params={"page_size": limit})
        return _extract_list(data)

    def get_product_by_id(self, product_id: int) -> dict | None:
        return self.get(f"/api/books/{product_id}/")

    def search_products(self, query: str, category: str | None = None,
                        min_price: float | None = None, max_price: float | None = None) -> list[dict]:
        params: dict = {"search": query}
        if category:
            params["category"] = category
        if min_price is not None:
            params["min_price"] = min_price
        if max_price is not None:
            params["max_price"] = max_price
        data = self.get("/api/books/", params=params)
        return _extract_list(data)

    def get_by_category(self, category: str) -> list[dict]:
        data = self.get("/api/books/", params={"category": category})
        return _extract_list(data)


catalog_client = CatalogServiceClient()
