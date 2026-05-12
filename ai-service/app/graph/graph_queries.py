from __future__ import annotations

from .neo4j_adapter import neo4j_adapter


def get_user_interested_products(user_id: int, limit: int = 10) -> list[dict]:
    query = """
    MATCH (u:User {id:$uid})-[r]->(p:Product)
    WHERE type(r) IN ['VIEWED','ADDED_TO_CART','PURCHASED','WISHLISTED','CLICKED_RECOMMENDATION']
    RETURN p.id AS product_id, coalesce(p.title, p.name, '') AS title, type(r) AS relation, coalesce(r.count,1) AS strength
    ORDER BY strength DESC
    LIMIT $limit
    """
    return neo4j_adapter.run(query, {"uid": user_id, "limit": limit})


def get_user_interested_categories(user_id: int, limit: int = 5) -> list[dict]:
    query = """
    MATCH (u:User {id:$uid})-[r]->(p:Product)-[:BELONGS_TO]->(s:SubCategory)-[:CHILD_OF]->(c:Category)
    WHERE type(r) IN ['VIEWED','ADDED_TO_CART','PURCHASED','WISHLISTED','CLICKED_RECOMMENDATION']
    RETURN c.slug AS category_slug, c.name AS category, sum(coalesce(r.count,1)) AS score
    ORDER BY score DESC
    LIMIT $limit
    """
    return neo4j_adapter.run(query, {"uid": user_id, "limit": limit})


def get_user_interested_subcategories(user_id: int, limit: int = 5) -> list[dict]:
    query = """
    MATCH (u:User {id:$uid})-[r]->(p:Product)-[:BELONGS_TO]->(s:SubCategory)
    WHERE type(r) IN ['VIEWED','ADDED_TO_CART','PURCHASED','WISHLISTED','CLICKED_RECOMMENDATION']
    RETURN s.slug AS subcategory_slug, s.name AS subcategory, sum(coalesce(r.count,1)) AS score
    ORDER BY score DESC
    LIMIT $limit
    """
    return neo4j_adapter.run(query, {"uid": user_id, "limit": limit})


def get_similar_products_by_behavior(user_id: int, limit: int = 10) -> list[dict]:
    query = """
    MATCH (u:User {id:$uid})-[:PURCHASED|ADDED_TO_CART|WISHLISTED|VIEWED]->(p:Product)-[s:SIMILAR_TO]->(rec:Product)
    WHERE rec.id <> p.id
    RETURN rec.id AS product_id, coalesce(rec.title, rec.name, '') AS title, sum(coalesce(s.score, 1.0)) AS support
    ORDER BY support DESC
    LIMIT $limit
    """
    return neo4j_adapter.run(query, {"uid": user_id, "limit": limit})


def get_top_recommended_products(user_id: int, limit: int = 10) -> list[dict]:
    query = """
    MATCH (u:User {id:$uid})-[r:VIEWED|ADDED_TO_CART|PURCHASED|WISHLISTED|CLICKED_RECOMMENDATION]->(p:Product)
    WITH collect(DISTINCT p.id) AS seen_ids, collect(DISTINCT p) AS seen_products
    UNWIND seen_products AS sp
    MATCH (sp)-[:BELONGS_TO]->(sub:SubCategory)<-[:BELONGS_TO]-(candidate:Product)
    WHERE NOT candidate.id IN seen_ids
    RETURN candidate.id AS product_id,
           coalesce(candidate.title, candidate.name, '') AS title,
           sub.name AS subcategory,
           count(*) AS score
    ORDER BY score DESC, product_id ASC
    LIMIT $limit
    """
    return neo4j_adapter.run(query, {"uid": user_id, "limit": limit})


def get_product_graph_context(product_id: int, limit: int = 5) -> dict[str, list[dict]]:
    category_query = """
    MATCH (p:Product {id:$pid})-[:BELONGS_TO]->(s:SubCategory)-[:CHILD_OF]->(c:Category)
    RETURN c.slug AS category_slug, c.name AS category, s.slug AS subcategory_slug, s.name AS subcategory
    LIMIT 1
    """
    similar = neo4j_adapter.run(
        """
        MATCH (p:Product {id:$pid})-[r:SIMILAR_TO]->(rec:Product)
        RETURN rec.id AS product_id, coalesce(rec.title, rec.name, '') AS title, coalesce(r.score, 0) AS score
        ORDER BY score DESC, product_id ASC
        LIMIT $limit
        """,
        {"pid": product_id, "limit": limit},
    )
    category = neo4j_adapter.run(category_query, {"pid": product_id})
    return {"similar": similar, "category": category}


def get_customer_graph_hints(user_id: int, limit: int = 6) -> list[str]:
    hints: list[str] = []
    for row in get_user_interested_categories(user_id, limit=3):
        name = row.get("category")
        if name:
            hints.append(str(name))
    for row in get_user_interested_subcategories(user_id, limit=3):
        name = row.get("subcategory")
        if name:
            hints.append(str(name))
    for row in get_user_interested_products(user_id, limit=3):
        title = row.get("title")
        if title:
            hints.append(str(title))
    return hints[:limit]
