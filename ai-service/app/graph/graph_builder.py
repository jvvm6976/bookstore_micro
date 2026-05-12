from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from ..clients.catalog_client import catalog_client
from .neo4j_adapter import neo4j_adapter

REL_BY_ACTION = {
    "search": "SEARCHED",
    "view": "VIEWED",
    "add_to_cart": "ADDED_TO_CART",
    "purchase": "PURCHASED",
    "rate_product": "RATED",
    "wishlist": "WISHLISTED",
    "remove_from_cart": "REMOVED_FROM_CART",
    "click": "CLICKED_RECOMMENDATION",
}

ACTION_WEIGHTS = {
    "SEARCHED": 1.0,
    "VIEWED": 1.5,
    "ADDED_TO_CART": 3.0,
    "PURCHASED": 5.0,
    "RATED": 2.0,
    "WISHLISTED": 2.5,
    "REMOVED_FROM_CART": -1.0,
    "CLICKED_RECOMMENDATION": 1.2,
}


def _slugify(value: str, fallback: str) -> str:
    text = (value or fallback).strip().lower()
    if not text:
        text = fallback
    return "-".join(part for part in text.replace("/", " ").replace("_", " ").split() if part)


def _load_catalog() -> dict[int, dict]:
    products: dict[int, dict] = {}
    try:
        for product in catalog_client.get_all_products(limit=1000):
            pid = product.get("id")
            if pid:
                products[int(pid)] = product
    except Exception:
        return {}
    return products


def _resolve_category(product: dict | None, action: str | None = None) -> tuple[str, str]:
    if not product:
        fallback = _slugify(action or "uncategorized", "uncategorized")
        return fallback, fallback.replace("-", " ")

    category_name = (
        product.get("category")
        or product.get("category_name")
        or product.get("category_slug")
        or "uncategorized"
    )
    category_slug = _slugify(str(category_name), "uncategorized")
    return category_slug, str(category_name)


def _resolve_subcategory(product: dict | None, category_slug: str) -> tuple[str, str]:
    if not product:
        return f"{category_slug}-general", "General"

    subcategory = (
        product.get("product_type")
        or product.get("subcategory")
        or product.get("brand")
        or product.get("author")
        or product.get("name")
        or product.get("title")
        or "General"
    )
    subcategory_name = str(subcategory).strip() or "General"
    return _slugify(subcategory_name, f"{category_slug}-general"), subcategory_name


def init_schema(clear_first: bool = False) -> None:
    if clear_first:
        neo4j_adapter.run_write("MATCH (n) DETACH DELETE n")

    constraints = [
        "CREATE CONSTRAINT IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Product) REQUIRE p.id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Category) REQUIRE c.slug IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (s:SubCategory) REQUIRE s.slug IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (b:Behavior) REQUIRE b.name IS UNIQUE",
    ]
    for q in constraints:
        neo4j_adapter.run_write(q)


def build_from_csv(csv_path: str | Path, clear_first: bool = False) -> dict[str, int]:
    # Reconnect in case adapter was initialized before Neo4j was ready
    neo4j_adapter._connect()
    
    if not neo4j_adapter.available:
        return {"users": 0, "products": 0, "categories": 0, "relations": 0}

    init_schema(clear_first=clear_first)

    users = set()
    products = set()
    categories = set()
    subcategories = set()
    rel_count = 0
    action_counts: dict[str, int] = defaultdict(int)
    user_products: dict[int, set[int]] = defaultdict(set)
    product_users: dict[int, set[int]] = defaultdict(set)
    user_pair_counts: dict[tuple[int, int], int] = defaultdict(int)
    product_pair_counts: dict[tuple[int, int], int] = defaultdict(int)
    catalog = _load_catalog()

    path = Path(csv_path)
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            user_id = int(float(row.get("user_id", 0) or 0))
            product_id = int(float(row.get("product_id", 0) or 0))
            action = str(row.get("action") or "search")
            ts = str(row.get("timestamp") or "")

            rel_type = REL_BY_ACTION.get(action)
            if not rel_type:
                continue

            product_meta = catalog.get(product_id, {})
            category_slug, category_name = _resolve_category(product_meta, action)
            subcategory_slug, subcategory_name = _resolve_subcategory(product_meta, category_slug)

            users.add(user_id)
            products.add(product_id)
            categories.add(category_slug)
            subcategories.add(subcategory_slug)
            user_products[user_id].add(product_id)
            product_users[product_id].add(user_id)
            action_counts[rel_type] += 1

            neo4j_adapter.run_write(
                "MERGE (u:User {id:$uid}) ON CREATE SET u.created_at = datetime()",
                {"uid": user_id},
            )
            neo4j_adapter.run_write(
                """
                MERGE (p:Product {id:$pid})
                ON CREATE SET
                    p.name = $name,
                    p.title = $title,
                    p.category_slug = $category_slug,
                    p.category = $category_name,
                    p.subcategory_slug = $subcategory_slug,
                    p.subcategory = $subcategory_name,
                    p.brand = $brand,
                    p.author = $author,
                    p.price = $price,
                    p.cover_image_url = $cover_image_url
                ON MATCH SET
                    p.name = coalesce(p.name, $name),
                    p.title = coalesce(p.title, $title),
                    p.category_slug = coalesce(p.category_slug, $category_slug),
                    p.category = coalesce(p.category, $category_name),
                    p.subcategory_slug = coalesce(p.subcategory_slug, $subcategory_slug),
                    p.subcategory = coalesce(p.subcategory, $subcategory_name),
                    p.brand = coalesce(p.brand, $brand),
                    p.author = coalesce(p.author, $author),
                    p.price = coalesce(p.price, $price),
                    p.cover_image_url = coalesce(p.cover_image_url, $cover_image_url)
                """,
                {
                    "pid": product_id,
                    "name": product_meta.get("name") or product_meta.get("title") or f"Product {product_id}",
                    "title": product_meta.get("title") or product_meta.get("name") or f"Product {product_id}",
                    "category_slug": category_slug,
                    "category_name": category_name,
                    "subcategory_slug": subcategory_slug,
                    "subcategory_name": subcategory_name,
                    "brand": product_meta.get("brand") or "",
                    "author": product_meta.get("author") or "",
                    "price": float(product_meta.get("price", 0) or 0),
                    "cover_image_url": product_meta.get("cover_image_url") or product_meta.get("cover_image") or "",
                },
            )
            neo4j_adapter.run_write(
                "MERGE (b:Behavior {name:$name})",
                {"name": action},
            )
            neo4j_adapter.run_write(
                """
                MERGE (cat:Category {slug:$slug})
                ON CREATE SET cat.name = $name
                MERGE (sub:SubCategory {slug:$sub_slug})
                ON CREATE SET sub.name = $sub_name
                MERGE (sub)-[:CHILD_OF]->(cat)
                MERGE (p:Product {id:$pid})
                MERGE (p)-[:BELONGS_TO]->(sub)
                """,
                {
                    "pid": product_id,
                    "slug": category_slug,
                    "name": category_name,
                    "sub_slug": subcategory_slug,
                    "sub_name": subcategory_name,
                },
            )

            query = (
                "MATCH (u:User {id:$uid}), (p:Product {id:$pid}), (b:Behavior {name:$action}) "
                f"MERGE (u)-[r:{rel_type}]->(p) "
                "ON CREATE SET r.count=1, r.last_ts=$ts "
                "ON MATCH SET r.count=r.count+1, r.last_ts=$ts "
                "MERGE (u)-[:PERFORMED]->(b)"
            )
            params = {
                "uid": user_id,
                "pid": product_id,
                "action": action,
                "ts": ts,
            }
            neo4j_adapter.run_write(query, params)

            rel_count += 1

    # Derive product and user similarity from co-interaction overlap.
    similarity_edges = 0
    for user_id, items in user_products.items():
        if len(items) < 2:
            continue
        item_list = sorted(items)
        for idx, left_id in enumerate(item_list):
            for right_id in item_list[idx + 1 :]:
                product_pair_counts[(left_id, right_id)] += 1
                neo4j_adapter.run_write(
                    """
                    MATCH (a:Product {id:$left_id}), (b:Product {id:$right_id})
                    MERGE (a)-[r:SIMILAR_TO]->(b)
                    ON CREATE SET r.score = 1.0, r.source = 'user_overlap'
                    ON MATCH SET r.score = coalesce(r.score, 0) + 0.25
                    MERGE (b)-[r2:SIMILAR_TO]->(a)
                    ON CREATE SET r2.score = 1.0, r2.source = 'user_overlap'
                    ON MATCH SET r2.score = coalesce(r2.score, 0) + 0.25
                    """,
                    {"left_id": left_id, "right_id": right_id},
                )
                similarity_edges += 2

    for (left_id, right_id), shared in product_pair_counts.items():
        if shared < 2:
            continue
        neo4j_adapter.run_write(
            """
            MATCH (a:Product {id:$left_id}), (b:Product {id:$right_id})
            MERGE (a)-[r:SIMILAR_TO]->(b)
            ON CREATE SET r.score = $score, r.source = 'shared_users'
            ON MATCH SET r.score = coalesce(r.score, 0) + $score * 0.1
            MERGE (b)-[r2:SIMILAR_TO]->(a)
            ON CREATE SET r2.score = $score, r2.source = 'shared_users'
            ON MATCH SET r2.score = coalesce(r2.score, 0) + $score * 0.1
            """,
            {"left_id": left_id, "right_id": right_id, "score": float(shared)},
        )
        similarity_edges += 2

    # Build customer-to-customer similarity from shared product interactions.
    similar_customer_edges = 0
    for product_id, interacted_users in product_users.items():
        users_list = sorted(interacted_users)
        if len(users_list) < 2:
            continue
        for idx, left_uid in enumerate(users_list):
            for right_uid in users_list[idx + 1 :]:
                user_pair_counts[(left_uid, right_uid)] += 1

    for (left_uid, right_uid), shared_products in user_pair_counts.items():
        if shared_products < 2:
            continue
        neo4j_adapter.run_write(
            """
            MATCH (u1:User {id:$left_uid}), (u2:User {id:$right_uid})
            MERGE (u1)-[r:SIMILAR_CUSTOMER]->(u2)
            ON CREATE SET r.shared_products = $shared_products, r.score = toFloat($shared_products), r.updated_at = datetime()
            ON MATCH SET r.shared_products = $shared_products, r.score = toFloat($shared_products), r.updated_at = datetime()
            """,
            {
                "left_uid": left_uid,
                "right_uid": right_uid,
                "shared_products": int(shared_products),
            },
        )
        similar_customer_edges += 1

    return {
        "users": len(users),
        "products": len(products),
        "categories": len(categories),
        "subcategories": len(subcategories),
        "relations": rel_count,
        "similarity_edges": similarity_edges,
        "similar_customer_edges": similar_customer_edges,
        "actions": dict(action_counts),
    }
