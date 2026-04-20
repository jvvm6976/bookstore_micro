from __future__ import annotations

import logging
import os
from collections import defaultdict
from typing import Any

from ..clients.catalog_client import catalog_client

logger = logging.getLogger(__name__)

try:
    from neo4j import GraphDatabase
except Exception:  # pragma: no cover - optional dependency
    GraphDatabase = None


def _book_category_key(book: dict) -> str:
    category_detail = book.get("category_detail")
    if isinstance(category_detail, dict):
        return str(category_detail.get("slug") or category_detail.get("name") or book.get("category") or "")
    return str(book.get("category") or "")


class Neo4jStore:
    def __init__(self):
        self.uri = os.getenv("NEO4J_URI", "")
        self.user = os.getenv("NEO4J_USER", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "neo4j_password")
        self._driver = None
        if GraphDatabase and self.uri:
            try:
                self._driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
                logger.info("Neo4j driver initialized: %s", self.uri)
            except Exception as exc:
                logger.warning("Neo4j unavailable; using local graph fallback: %s", exc)
                self._driver = None

    @property
    def available(self) -> bool:
        return self._driver is not None

    def sync_catalog(self, products: list[dict[str, Any]]) -> int:
        if not self._driver:
            return len(products)
        try:
            with self._driver.session() as session:
                for product in products:
                    session.run(
                        """
                        MERGE (p:Product {product_id: $product_id})
                        SET p.title = $title, p.category = $category, p.brand = $brand, p.product_type = $product_type, p.price = $price
                        MERGE (c:Category {slug: $category})
                        MERGE (b:Brand {slug: $brand})
                        MERGE (t:ProductType {slug: $product_type})
                        MERGE (p)-[:IN_CATEGORY]->(c)
                        MERGE (p)-[:IN_BRAND]->(b)
                        MERGE (p)-[:IN_TYPE]->(t)
                        """,
                        product_id=int(product.get("id") or 0),
                        title=str(product.get("title") or product.get("name") or ""),
                        category=_book_category_key(product),
                        brand=str(product.get("brand_detail", {}).get("slug") if isinstance(product.get("brand_detail"), dict) else product.get("brand") or ""),
                        product_type=str(product.get("type_detail", {}).get("slug") if isinstance(product.get("type_detail"), dict) else product.get("product_type") or ""),
                        price=float(product.get("price", 0) or 0),
                    )
            return len(products)
        except Exception as exc:
            logger.warning("Neo4j sync failed; falling back to local graph scoring: %s", exc)
            return len(products)

    def score_candidates(
        self,
        customer_id: int,
        seed_product_ids: list[int],
        candidate_products: list[dict[str, Any]],
    ) -> dict[int, dict[str, Any]]:
        if not candidate_products:
            return {}

        seed_products = [catalog_client.get_product_by_id(pid) for pid in seed_product_ids]
        seed_products = [p for p in seed_products if p]
        score_map: dict[int, dict[str, Any]] = defaultdict(lambda: {"score": 0.0, "reason": "graph fallback"})

        seed_categories = { _book_category_key(p) for p in seed_products if _book_category_key(p) }
        seed_brands = {
            str(p.get("brand_detail", {}).get("slug") if isinstance(p.get("brand_detail"), dict) else p.get("brand") or "")
            for p in seed_products
            if (p.get("brand_detail") or p.get("brand"))
        }
        seed_types = {
            str(p.get("type_detail", {}).get("slug") if isinstance(p.get("type_detail"), dict) else p.get("product_type") or "")
            for p in seed_products
            if (p.get("type_detail") or p.get("product_type"))
        }

        for product in candidate_products:
            pid = int(product.get("id") or 0)
            if not pid:
                continue
            category = _book_category_key(product)
            brand = str(product.get("brand_detail", {}).get("slug") if isinstance(product.get("brand_detail"), dict) else product.get("brand") or "")
            product_type = str(product.get("type_detail", {}).get("slug") if isinstance(product.get("type_detail"), dict) else product.get("product_type") or "")

            score = 0.0
            reasons = []
            if category and category in seed_categories:
                score += 1.8
                reasons.append(f"cùng hệ category với hành vi gần đây: {category}")
            if brand and brand in seed_brands:
                score += 1.2
                reasons.append(f"cùng brand với lựa chọn trước: {brand}")
            if product_type and product_type in seed_types:
                score += 1.1
                reasons.append(f"cùng loại sản phẩm: {product_type}")

            score_map[pid] = {
                "score": round(score, 3),
                "reason": "; ".join(reasons) if reasons else "đồ thị tri thức không có liên hệ mạnh",
            }

        return score_map


neo4j_store = Neo4jStore()
