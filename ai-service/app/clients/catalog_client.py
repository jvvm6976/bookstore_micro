"""CatalogServiceClient — proxies to product-service (DDD source of truth).
Đây là client chính thay thế book_client cũ.
"""
from __future__ import annotations
from .base import ServiceClient, _extract_list
from ..core.config import PRODUCT_SERVICE_URL


def _normalize_product(item: dict) -> dict:
    """Normalize product-service payload to AI service recommendation schema.

    Product-service serializer returns:
      id, name, description, sku, price, stock, status,
      category_id, category_name, domain_id, domain_name, image_url,
      book: {author, publisher, isbn},
      electronics: {brand, warranty_months},
      fashion: {size, color}
    """
    # author lives inside nested book{} object
    book_data = item.get("book") or {}
    author = book_data.get("author") or ""

    # category is returned as category_name (human-readable string)
    category = item.get("category_name") or item.get("category") or ""

    # brand lives inside nested electronics{} object
    electronics_data = item.get("electronics") or {}
    brand = electronics_data.get("brand") or ""

    return {
        "id":              item.get("id"),
        "product_id":      item.get("id"),
        # product-service uses "name"; keep "title" alias for AI-internal use
        "name":            item.get("name") or "",
        "title":           item.get("name") or "",
        "author":          author,
        "brand":           brand,
        "category":        category,
        "category_id":     item.get("category_id"),
        "domain_id":       item.get("domain_id"),
        "domain_name":     item.get("domain_name") or "",
        "sku":             item.get("sku") or "",
        "price":           float(item.get("price") or 0),
        "stock":           int(item.get("stock") or 0),
        "status":          item.get("status") or "",
        "description":     item.get("description") or "",
        # product-service uses image_url (not cover_image_url)
        "image_url":       item.get("image_url") or "",
        "cover_image_url": item.get("image_url") or "",
    }


def _matches_category(product: dict, category_slug: str | None) -> bool:
    if not category_slug:
        return True
    wanted = str(category_slug).strip().lower()
    tags = {
        str(product.get("category", "")).strip().lower(),
        str(product.get("domain_name", "")).strip().lower(),
    }
    return wanted in tags


class ProductServiceClient(ServiceClient):
    """HTTP client for product-service (DDD). Replaces old book_client."""

    def __init__(self):
        super().__init__(PRODUCT_SERVICE_URL, "product-service")

    def get_all_products(self, limit: int = 200, category_slug: str | None = None) -> list[dict]:
        params: dict = {}
        if category_slug:
            params["keyword"] = category_slug
        data = self.get("/products/", params=params or None)
        return [_normalize_product(i) for i in _extract_list(data)][:limit]

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
            params["keyword"] = f"{params.get('keyword', '')} {product_type}".strip()
        if in_stock:
            params["status"] = "active"
        data = self.get("/products/", params=params)
        products = [_normalize_product(i) for i in _extract_list(data)]
        if category_slug:
            products = [p for p in products if _matches_category(p, category_slug)]
        if min_price is not None:
            products = [p for p in products if p["price"] >= min_price]
        if max_price is not None:
            products = [p for p in products if p["price"] <= max_price]
        if in_stock:
            products = [p for p in products if p["stock"] > 0]
        return products

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
