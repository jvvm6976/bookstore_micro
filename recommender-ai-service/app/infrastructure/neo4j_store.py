from __future__ import annotations

import csv
import logging
import os
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from ..clients.catalog_client import catalog_client
from ..core.config import GRAPH_BOOTSTRAP_FROM_TRAIN, TRAIN_DATA_PATH

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
        self.train_data_path = Path(os.getenv("TRAIN_DATA_PATH", str(TRAIN_DATA_PATH)))
        self.graph_bootstrap_from_train = os.getenv(
            "GRAPH_BOOTSTRAP_FROM_TRAIN",
            "1" if GRAPH_BOOTSTRAP_FROM_TRAIN else "0",
        ) == "1"
        self._driver = None
        self._train_graph_bootstrapped = False
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

    def _normalize_product_id(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, int):
            return str(int(value))
        raw = str(value).strip()
        if not raw:
            return ""
        if raw.isdigit():
            return str(int(raw))
        match = re.findall(r"\d+", raw)
        if match:
            try:
                return str(int(match[0]))
            except ValueError:
                pass
        return raw.lower()

    def _parse_train_rows(self) -> list[tuple[str, str, datetime]]:
        if not self.train_data_path.exists():
            return []
        rows: list[tuple[str, str, datetime]] = []
        with self.train_data_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                user_id = str(row.get("user_id") or "").strip()
                product_id = self._normalize_product_id(row.get("product_id"))
                ts_raw = str(row.get("timestamp") or "").strip()
                if not user_id or not product_id or not ts_raw:
                    continue
                try:
                    ts = datetime.fromisoformat(ts_raw)
                except ValueError:
                    continue
                rows.append((user_id, product_id, ts))
        return rows

    def ensure_train_graph(self) -> dict[str, Any]:
        if self._train_graph_bootstrapped:
            return {"status": "cached"}
        if not self._driver:
            return {"status": "neo4j-unavailable"}
        if not self.graph_bootstrap_from_train:
            return {"status": "disabled"}
        if not self.train_data_path.exists():
            logger.warning("Training data not found for graph bootstrap: %s", self.train_data_path)
            return {"status": "missing-train-data", "path": str(self.train_data_path)}

        rows = self._parse_train_rows()
        if not rows:
            return {"status": "no-train-rows", "path": str(self.train_data_path)}

        rows.sort(key=lambda item: (item[0], item[2]))
        pair_counts: dict[tuple[str, str], int] = defaultdict(int)
        popularity: dict[str, int] = defaultdict(int)

        for _, product_id, _ in rows:
            popularity[product_id] += 1

        prev_user = ""
        prev_ts: datetime | None = None
        prev_product = ""
        for user_id, product_id, ts in rows:
            if prev_user == user_id and prev_ts is not None:
                delta_seconds = (ts - prev_ts).total_seconds()
                if 0 <= delta_seconds <= 7200 and prev_product and product_id and prev_product != product_id:
                    p1, p2 = sorted((prev_product, product_id))
                    pair_counts[(p1, p2)] += 1
            prev_user = user_id
            prev_ts = ts
            prev_product = product_id

        try:
            with self._driver.session() as session:
                for product_id, pop in popularity.items():
                    session.run(
                        """
                        MERGE (p:Product {product_id: $product_id})
                        SET p.train_popularity = $train_popularity
                        """,
                        product_id=product_id,
                        train_popularity=int(pop),
                    )
                for (pid1, pid2), weight in pair_counts.items():
                    session.run(
                        """
                        MATCH (p1:Product {product_id: $pid1})
                        MATCH (p2:Product {product_id: $pid2})
                        MERGE (p1)-[r:SIMILAR_TO]-(p2)
                        SET r.weight = $weight,
                            r.source = 'train_data'
                        """,
                        pid1=pid1,
                        pid2=pid2,
                        weight=int(weight),
                    )
            self._train_graph_bootstrapped = True
            logger.info(
                "Bootstrapped graph from train data: products=%d pairs=%d path=%s",
                len(popularity),
                len(pair_counts),
                self.train_data_path,
            )
            return {
                "status": "ok",
                "products": len(popularity),
                "pairs": len(pair_counts),
                "path": str(self.train_data_path),
            }
        except Exception as exc:
            logger.warning("Failed to bootstrap graph from train data: %s", exc)
            return {"status": "error", "error": str(exc)}

    def sync_customer_behavior(self, customer_id: int, interactions: dict[str, dict[int, int]]) -> int:
        if not self._driver or not customer_id:
            return 0

        total = 0
        seen_product_ids: set[str] = set()
        try:
            with self._driver.session() as session:
                session.run(
                    """
                    MERGE (u:Customer {customer_id: $customer_id})
                    """,
                    customer_id=int(customer_id),
                )
                for action, book_counts in (interactions or {}).items():
                    if not isinstance(book_counts, dict):
                        continue
                    for raw_pid, count in book_counts.items():
                        product_id = self._normalize_product_id(raw_pid)
                        if not product_id:
                            continue
                        seen_product_ids.add(product_id)
                        total += int(count or 0)
                        session.run(
                            """
                            MERGE (u:Customer {customer_id: $customer_id})
                            MERGE (p:Product {product_id: $product_id})
                            MERGE (u)-[r:INTERACTED]->(p)
                            SET r.weight = coalesce(r.weight, 0) + $weight,
                                r.last_action = $last_action
                            """,
                            customer_id=int(customer_id),
                            product_id=product_id,
                            weight=int(count or 0),
                            last_action=str(action),
                        )

                seed_ids = sorted(seen_product_ids)
                for idx in range(len(seed_ids)):
                    for jdx in range(idx + 1, len(seed_ids)):
                        session.run(
                            """
                            MATCH (p1:Product {product_id: $pid1})
                            MATCH (p2:Product {product_id: $pid2})
                            MERGE (p1)-[r:SIMILAR_TO]-(p2)
                            SET r.weight = coalesce(r.weight, 0) + 1,
                                r.source = coalesce(r.source, 'runtime_behavior')
                            """,
                            pid1=seed_ids[idx],
                            pid2=seed_ids[jdx],
                        )
        except Exception as exc:
            logger.warning("Could not sync customer behavior to graph: %s", exc)
            return 0

        return total

    def sync_catalog(self, products: list[dict[str, Any]]) -> int:
        if not self._driver:
            return len(products)
        try:
            with self._driver.session() as session:
                for product in products:
                    normalized_pid = self._normalize_product_id(product.get("id"))
                    if not normalized_pid:
                        continue
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
                        product_id=normalized_pid,
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

        if self._driver:
            try:
                candidate_map = {
                    int(product.get("id") or 0): self._normalize_product_id(product.get("id"))
                    for product in candidate_products
                    if int(product.get("id") or 0) > 0
                }
                inverse_map = {v: k for k, v in candidate_map.items() if v}
                seed_ids = [self._normalize_product_id(pid) for pid in seed_product_ids if self._normalize_product_id(pid)]
                candidate_ids = [pid for pid in candidate_map.values() if pid]

                graph_result: dict[int, dict[str, Any]] = {}
                with self._driver.session() as session:
                    if seed_ids and candidate_ids:
                        records = session.run(
                            """
                            UNWIND $seed_ids AS sid
                            MATCH (s:Product {product_id: sid})-[r:SIMILAR_TO]-(c:Product)
                            WHERE c.product_id IN $candidate_ids AND c.product_id <> sid
                            WITH c.product_id AS pid, sum(coalesce(r.weight, 0)) AS score
                            RETURN pid, score
                            ORDER BY score DESC
                            """,
                            seed_ids=seed_ids,
                            candidate_ids=candidate_ids,
                        )
                        for record in records:
                            mapped_id = inverse_map.get(str(record["pid"]))
                            if not mapped_id:
                                continue
                            score = float(record["score"] or 0.0)
                            graph_result[mapped_id] = {
                                "score": round(score, 3),
                                "reason": "liên hệ đồ thị từ dữ liệu train + hành vi người dùng",
                            }

                    if customer_id and candidate_ids:
                        records = session.run(
                            """
                            MATCH (u:Customer {customer_id: $customer_id})-[iu:INTERACTED]->(:Product)-[r:SIMILAR_TO]-(c:Product)
                            WHERE c.product_id IN $candidate_ids
                            WITH c.product_id AS pid, sum(coalesce(iu.weight, 0) * coalesce(r.weight, 0)) AS score
                            RETURN pid, score
                            ORDER BY score DESC
                            """,
                            customer_id=int(customer_id),
                            candidate_ids=candidate_ids,
                        )
                        for record in records:
                            mapped_id = inverse_map.get(str(record["pid"]))
                            if not mapped_id:
                                continue
                            add_score = float(record["score"] or 0.0)
                            payload = graph_result.setdefault(
                                mapped_id,
                                {"score": 0.0, "reason": "liên hệ đồ thị từ dữ liệu train + hành vi người dùng"},
                            )
                            payload["score"] = round(float(payload.get("score", 0.0)) + add_score, 3)

                if graph_result:
                    return graph_result
            except Exception as exc:
                logger.warning("Neo4j graph scoring failed; fallback to local scoring: %s", exc)

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
