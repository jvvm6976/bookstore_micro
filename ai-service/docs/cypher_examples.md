# Cypher Examples for KB Graph

## 1) San pham user quan tam

```cypher
MATCH (u:User {id: 12})-[r]->(p:Product)
WHERE type(r) IN ['VIEWED','ADDED_TO_CART','PURCHASED','WISHLISTED','CLICKED_RECOMMENDATION']
RETURN p.id AS product_id, type(r) AS relation, coalesce(r.count,1) AS strength
ORDER BY strength DESC
LIMIT 10;
```

## 2) Category user quan tam

```cypher
MATCH (u:User {id: 12})-[r]->(p:Product)-[:BELONGS_TO]->(c:Category)
WHERE type(r) IN ['VIEWED','ADDED_TO_CART','PURCHASED','WISHLISTED','CLICKED_RECOMMENDATION']
RETURN c.name AS category, sum(coalesce(r.count,1)) AS score
ORDER BY score DESC
LIMIT 5;
```

## 3) San pham tuong tu theo hanh vi

```cypher
MATCH (u:User {id: 12})-[:PURCHASED|ADDED_TO_CART|WISHLISTED]->(p:Product)
MATCH (p)<-[:PURCHASED|ADDED_TO_CART|WISHLISTED]-(other:User)-[:PURCHASED|ADDED_TO_CART|WISHLISTED]->(rec:Product)
WHERE other.id <> 12 AND rec.id <> p.id
RETURN rec.id AS product_id, count(DISTINCT other) AS support
ORDER BY support DESC
LIMIT 10;
```

## 4) Top recommended products

```cypher
MATCH (u:User {id: 12})-[r:VIEWED|ADDED_TO_CART|PURCHASED|WISHLISTED|CLICKED_RECOMMENDATION]->(p:Product)
WITH u, collect(p.id) AS seen, collect(distinct p) AS seen_products
UNWIND seen_products AS sp
MATCH (sp)-[:BELONGS_TO]->(c:Category)<-[:BELONGS_TO]-(candidate:Product)
WHERE NOT candidate.id IN seen
RETURN candidate.id AS product_id, c.name AS category, count(*) AS score
ORDER BY score DESC
LIMIT 10;
```
