"""
Neo4j Knowledge Graph Adapter
──────────────────────────────
Schema (Product-centric, multi-domain):
  Nodes:  Customer, Product, Category, Brand
  Rels:   SEARCHED, VIEWED, ADDED_TO_CART, PURCHASED, RATED,
      WISHLISTED, REMOVED_FROM_CART, CLICKED_RECOMMENDATION,
      BELONGS_TO, SIMILAR_TO

Graceful fallback: nếu Neo4j không kết nối được, tất cả methods trả về
empty results và log WARNING — không raise exception.

Graph score được dùng trong hybrid recommendation:
  final_score = w1 * lstm_score + w2 * graph_score + w3 * rag_score
"""
from __future__ import annotations
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://neo4j:7687")
NEO4J_USER     = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j_password")

INIT_QUERIES = [
    "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Customer) REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Product) REQUIRE p.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (cat:Category) REQUIRE cat.slug IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (b:Brand) REQUIRE b.name IS UNIQUE",
]

# Collaborative filtering: customers who bought X also bought Y
COLLAB_QUERY = """
MATCH (c:Customer {id: $customer_id})-[:PURCHASED|ADDED_TO_CART|WISHLISTED]->(p:Product)
    <-[:PURCHASED|ADDED_TO_CART|WISHLISTED]-(similar:Customer)-[:PURCHASED|ADDED_TO_CART|WISHLISTED]->(rec:Product)
WHERE NOT (c)-[:PURCHASED]->(rec)
  AND NOT (c)-[:VIEWED]->(rec)
RETURN rec.id AS product_id, COUNT(similar) AS support
ORDER BY support DESC
LIMIT $limit
"""

# Products in same category (graph-based)
SIMILAR_PRODUCTS_QUERY = """
MATCH (p:Product {id: $product_id})-[:BELONGS_TO]->(cat:Category)
      <-[:BELONGS_TO]-(similar:Product)
WHERE similar.id <> $product_id
RETURN similar.id AS product_id, similar.name AS name, 1 AS support
LIMIT $limit
"""

# Graph score for a specific product given customer context
GRAPH_SCORE_QUERY = """
MATCH (c:Customer {id: $customer_id})-[r]->(p:Product {id: $product_id})
RETURN type(r) AS rel_type, count(r) AS cnt
"""


class Neo4jAdapter:
    def __init__(self):
        self._driver = None
        self._available = False
        self._connect()

    def _connect(self) -> None:
        try:
            from neo4j import GraphDatabase
            self._driver = GraphDatabase.driver(
                NEO4J_URI,
                auth=(NEO4J_USER, NEO4J_PASSWORD),
            )
            self._driver.verify_connectivity()
            self._available = True
            self._init_schema()
            logger.info("Neo4j connected at %s", NEO4J_URI)
        except Exception as exc:
            logger.warning("Neo4j unavailable: %s — graph features disabled", exc)
            self._driver = None
            self._available = False

    def is_available(self) -> bool:
        return self._available

    def _init_schema(self) -> None:
        if not self._driver:
            return
        try:
            with self._driver.session() as session:
                for q in INIT_QUERIES:
                    session.run(q)
        except Exception as exc:
            logger.warning("Neo4j schema init failed: %s", exc)

    # ── Write interactions ────────────────────────────────────────────────────

    def write_interaction(
        self,
        customer_id: int,
        product_id: int,
        rel_type: str,
        props: dict | None = None,
        product_meta: dict | None = None,
    ) -> None:
        """Write Customer→Product relationship. Fire-and-forget."""
        if not self._available or not self._driver:
            return
        props = props or {}
        product_meta = product_meta or {}
        rel_type = rel_type.upper()
        if rel_type not in (
            "SEARCHED",
            "VIEWED",
            "ADDED_TO_CART",
            "PURCHASED",
            "RATED",
            "WISHLISTED",
            "REMOVED_FROM_CART",
            "CLICKED_RECOMMENDATION",
            "CART",
        ):
            return

        if rel_type == "CART":
            rel_type = "ADDED_TO_CART"

        try:
            with self._driver.session() as session:
                session.run("MERGE (c:Customer {id: $cid})", cid=customer_id)
                session.run(
                    "MERGE (p:Product {id: $pid}) "
                    "ON CREATE SET p.name=$name, p.category=$cat, p.brand=$brand, p.price=$price",
                    pid=product_id,
                    name=product_meta.get("name") or product_meta.get("title", ""),
                    cat=product_meta.get("category", ""),
                    brand=product_meta.get("brand", ""),
                    price=float(product_meta.get("price", 0)),
                )
                # Category node
                if product_meta.get("category"):
                    session.run(
                        "MERGE (cat:Category {slug: $slug}) ON CREATE SET cat.name=$name",
                        slug=product_meta["category"],
                        name=product_meta["category"],
                    )
                    session.run(
                        "MATCH (p:Product {id: $pid}), (cat:Category {slug: $cat}) "
                        "MERGE (p)-[:BELONGS_TO]->(cat)",
                        pid=product_id, cat=product_meta["category"],
                    )
                # Relationship
                REL_CYPHER = {
                    "SEARCHED":  "MERGE (c)-[r:SEARCHED]->(p) ON CREATE SET r.count=1,r.ts=$ts ON MATCH SET r.count=r.count+1,r.ts=$ts",
                    "VIEWED":    "MERGE (c)-[r:VIEWED]->(p) ON CREATE SET r.count=1,r.ts=$ts ON MATCH SET r.count=r.count+1,r.ts=$ts",
                    "ADDED_TO_CART": "MERGE (c)-[r:ADDED_TO_CART]->(p) ON CREATE SET r.count=1,r.ts=$ts ON MATCH SET r.count=r.count+1,r.ts=$ts",
                    "PURCHASED": "MERGE (c)-[r:PURCHASED]->(p) ON CREATE SET r.ts=$ts,r.price=$price ON MATCH SET r.ts=$ts",
                    "RATED":     "MERGE (c)-[r:RATED]->(p) ON CREATE SET r.rating=$rating ON MATCH SET r.rating=$rating",
                    "WISHLISTED": "MERGE (c)-[r:WISHLISTED]->(p) ON CREATE SET r.count=1,r.ts=$ts ON MATCH SET r.count=r.count+1,r.ts=$ts",
                    "REMOVED_FROM_CART": "MERGE (c)-[r:REMOVED_FROM_CART]->(p) ON CREATE SET r.count=1,r.ts=$ts ON MATCH SET r.count=r.count+1,r.ts=$ts",
                    "CLICKED_RECOMMENDATION": "MERGE (c)-[r:CLICKED_RECOMMENDATION]->(p) ON CREATE SET r.count=1,r.ts=$ts ON MATCH SET r.count=r.count+1,r.ts=$ts",
                }
                cypher = REL_CYPHER.get(rel_type)
                if cypher:
                    session.run(
                        f"MATCH (c:Customer {{id: $cid}}), (p:Product {{id: $pid}}) {cypher}",
                        cid=customer_id, pid=product_id,
                        ts=props.get("timestamp", 0),
                        price=float(props.get("price", 0)),
                        rating=int(props.get("rating", 0)),
                    )
        except Exception as exc:
            logger.warning("Neo4j write_interaction failed: %s", exc)

    # ── Read queries ──────────────────────────────────────────────────────────

    def get_collaborative_recs(self, customer_id: int, limit: int = 6) -> list[dict[str, Any]]:
        """Collaborative filtering: customers who bought X also bought Y."""
        if not self._available or not self._driver:
            return []
        try:
            with self._driver.session() as session:
                result = session.run(COLLAB_QUERY, customer_id=customer_id, limit=limit)
                return [{"product_id": r["product_id"], "support": r["support"]} for r in result]
        except Exception as exc:
            logger.warning("Neo4j collaborative query failed: %s", exc)
            return []

    def get_similar_products(self, product_id: int, limit: int = 6) -> list[dict]:
        """Products in same category from graph."""
        if not self._available or not self._driver:
            return []
        try:
            with self._driver.session() as session:
                result = session.run(SIMILAR_PRODUCTS_QUERY, product_id=product_id, limit=limit)
                return [{"product_id": r["product_id"], "name": r["name"]} for r in result]
        except Exception as exc:
            logger.warning("Neo4j similar_products query failed: %s", exc)
            return []

    def get_graph_scores(self, customer_id: int, product_ids: list[int]) -> dict[int, float]:
        """
        Compute graph-based affinity score for each product_id.
        Score = weighted sum of relationship counts.
        Used in hybrid scoring: final_score = w1*lstm + w2*graph + w3*rag
        """
        if not self._available or not self._driver or not product_ids:
            return {}

        REL_WEIGHTS = {
            "SEARCHED": 0.8,
            "VIEWED": 1.0,
            "ADDED_TO_CART": 3.0,
            "PURCHASED": 6.0,
            "RATED": 2.0,
            "WISHLISTED": 2.5,
            "REMOVED_FROM_CART": -1.0,
            "CLICKED_RECOMMENDATION": 1.8,
            "CART": 3.0,
        }
        scores: dict[int, float] = {}

        try:
            with self._driver.session() as session:
                # Batch query: get all relationships for this customer to these products
                result = session.run(
                    """
                    MATCH (c:Customer {id: $cid})-[r]->(p:Product)
                    WHERE p.id IN $pids
                    RETURN p.id AS product_id, type(r) AS rel_type, r.count AS cnt
                    """,
                    cid=customer_id,
                    pids=product_ids,
                )
                for row in result:
                    pid = row["product_id"]
                    rel = row["rel_type"]
                    cnt = float(row["cnt"] or 1)
                    w = REL_WEIGHTS.get(rel, 1.0)
                    scores[pid] = scores.get(pid, 0.0) + w * cnt
        except Exception as exc:
            logger.warning("Neo4j get_graph_scores failed: %s", exc)

        return scores

    def close(self) -> None:
        if self._driver:
            self._driver.close()


# Singleton
neo4j_adapter = Neo4jAdapter()
