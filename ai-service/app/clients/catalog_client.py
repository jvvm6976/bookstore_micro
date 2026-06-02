"""CatalogServiceClient — proxies to product-service (DDD source of truth).
Đây là client chính thay thế book_client cũ.
"""
from __future__ import annotations
from .base import ServiceClient, _extract_list
from ..core.config import PRODUCT_SERVICE_URL


def _normalize_product(item: dict) -> dict:
    """Normalize product-service payload to AI service recommendation schema."""
    attrs = item.get("attributes") or {}
    # Support both book-style (author) and generic product
    author = item.get("author") or attrs.get("author") or ""
    category = item.get("category_name") or item.get("category_slug") or item.get("category") or ""
    brand = item.get("brand_name") or attrs.get("brand") or ""
    product_type = item.get("product_type_name") or ""
    return {
        "id":              item.get("id"),
        "product_id":      item.get("id"),
        "title":           item.get("title") or item.get("name") or "",
        "name":            item.get("name") or item.get("title") or "",
        "author":          author,
        "brand":           brand,
        "category":        category,
        "category_name":   item.get("category_name") or category,
        "category_slug":   item.get("category_slug") or "",
        "domain_id":       item.get("domain_id"),
        "domain_name":     item.get("domain_name") or "",
        "product_type":    product_type,
        "sku":             item.get("sku") or "",
        "price":           float(item.get("price") or 0),
        "stock":           item.get("stock", 0),
        "description":     item.get("description", ""),
        "image_url":       item.get("image_url") or item.get("cover_image_url") or item.get("cover_image") or "",
        "cover_image_url": item.get("cover_image_url") or item.get("cover_image") or item.get("image_url") or "",
        "attributes":      attrs,
    }


class ProductServiceClient(ServiceClient):
    """HTTP client for product-service (DDD). Replaces old book_client."""

    def __init__(self):
        super().__init__(PRODUCT_SERVICE_URL, "product-service")

    def get_all_products(self, limit: int = 200, category_slug: str | None = None) -> list[dict]:
        params: dict = {}
        if category_slug:
            params["keyword"] = category_slug
        products: list[dict] = []
        page = 1
        while len(products) < limit and page <= 50:
            data = self.get("/products/", params={**params, "page": page})
            batch = _extract_list(data)
            products.extend(_normalize_product(i) for i in batch)
            if not isinstance(data, dict) or not data.get("next") or not batch:
                break
            page += 1
        return products[:limit]

    def get_product_by_id(self, product_id: int) -> dict | None:
        data = self.get(f"/products/{product_id}/")
        return _normalize_product(data) if data else None

    def search_products(
        self,
        query: str,
        category_slug: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        product_type: str | None = None,
        in_stock: bool = False,
    ) -> list[dict]:
        params: dict = {"keyword": query}
        if category_slug:
            params["keyword"] = f"{query} {category_slug}".strip()
        if min_price is not None:
            params["min_price"] = min_price
        if max_price is not None:
            params["max_price"] = max_price
        if product_type:
            params["product_type_name"] = product_type
        if in_stock:
            params["in_stock"] = "true"
        data = self.get("/products/", params=params)
        return [_normalize_product(i) for i in _extract_list(data)]

    def get_by_category(self, category_slug: str) -> list[dict]:
        data = self.get("/products/", params={"keyword": category_slug})
        return [_normalize_product(i) for i in _extract_list(data)]

    def get_categories(self) -> list[dict]:
        data = self.get("/categories/")
        return _extract_list(data)

    def health(self) -> dict:
        return self.get("/domains/") or {}


# Singleton — primary product client
product_client = ProductServiceClient()

# Backward-compat alias (catalog_client was used in older code)
catalog_client = product_client
