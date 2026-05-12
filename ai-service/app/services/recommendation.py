"""
RecommendationService — Hybrid Engine
──────────────────────────────────────
final_score = w1 * lstm_behavior + w2 * graph_score + w3 * content_affinity + w4 * rating_popularity

Components:
  1. LSTM behavior score  (w1=0.40) — sequence-based propensity
  2. Graph score          (w2=0.25) — Neo4j collaborative filtering
  3. Content affinity     (w3=0.25) — category/brand match
  4. Rating popularity    (w4=0.10) — community ratings

Each recommendation includes a human-readable reason (explainability).
"""
from __future__ import annotations
import logging
import math
from collections import defaultdict
from typing import Any

from ..clients.catalog_client import catalog_client
from ..clients.order_client import order_client
from ..clients.comment_client import comment_client
from ..core.config import PURCHASE_THRESHOLD, RECOMMENDATION_LIMIT
from .behavior_analysis import behavior_service
from ..infrastructure.graph.neo4j_adapter import neo4j_adapter

logger = logging.getLogger(__name__)

WEIGHTS = {
    "search": 2,
    "view": 1,
    "view_detail": 1,
    "cart": 4,
    "add_to_cart": 4,
    "purchase": 8,
    "rate": 3,
    "rate_product": 3,
    "wishlist": 3,
    "remove_from_cart": -2,
    "click_recommendation": 2,
}

# Hybrid weight constants
W_LSTM    = 0.40   # LSTM behavior propensity
W_GRAPH   = 0.25   # Neo4j graph collaborative score
W_CONTENT = 0.25   # Content-based affinity (category/brand)
W_RATING  = 0.10   # Community rating popularity


def _matches_category(product: dict, category: str | None) -> bool:
    if not category:
        return True
    wanted = str(category).strip().lower()
    tags = {
        str(product.get("category", "")).strip().lower(),
        str(product.get("domain_name", "")).strip().lower(),
    }
    return wanted in tags


def _get_purchased_ids(customer_id: int) -> set[int]:
    orders = order_client.get_orders_by_customer(customer_id)
    ids: set[int] = set()
    for order in orders:
        for item in order.get("items", []):
            # order-service OrderItem uses product_id
            pid = item.get("product_id")
            if pid:
                ids.add(int(pid))
    return ids


def _rating_map(product_ids: list[int]) -> dict[int, dict]:
    return comment_client.get_reviews_for_products(product_ids)


def _popularity_score(product_id: int, ratings: dict[int, dict]) -> float:
    rm = ratings.get(product_id, {})
    if not rm.get("count", 0):
        return 0.0
    return (rm["avg"] / 5.0) * math.log1p(rm["count"]) * 0.3


def get_personalized(
    customer_id: int,
    interactions: dict[str, dict[int, int]],   # {type: {product_id: count}}
    limit: int = RECOMMENDATION_LIMIT,
    budget_min: float | None = None,
    budget_max: float | None = None,
    category: str | None = None,
    customer_ratings: dict[int, int] | None = None,
    event_sequence: list[dict] | None = None,  # for LSTM behavior analysis
) -> list[dict[str, Any]]:
    """
    Generate personalized recommendations using hybrid scoring:
      final_score = w1 * lstm_behavior + w2 * content_affinity + w3 * rating_popularity
    """
    customer_ratings = customer_ratings or {}
    # Flatten to {product_id: weighted_score}
    book_scores: dict[int, float] = defaultdict(float)
    for itype, book_counts in interactions.items():
        w = WEIGHTS.get(itype, 1)
        for bid, cnt in book_counts.items():
            book_scores[bid] += w * cnt

    interaction_totals = {
        itype: sum(book_counts.values())
        for itype, book_counts in interactions.items()
    }

    # Use behavior profile signals to avoid one-size-fits-all recommendations.
    propensity = 0.0
    segment = "casual"
    profile_pref_cats: set[str] = set()
    try:
        profile = behavior_service.analyze(
            customer_id, interaction_totals,
            event_sequence=event_sequence,
        )
        propensity = float(profile.get("purchase_propensity_score", 0.0) or 0.0)
        segment = str(profile.get("customer_segment", "casual") or "casual")
        profile_pref_cats = {
            c.get("category")
            for c in profile.get("preferred_categories", [])
            if isinstance(c, dict) and c.get("category")
        }
    except Exception as exc:
        logger.debug("Behavior profile unavailable for C%s: %s", customer_id, exc)

    purchased = _get_purchased_ids(customer_id)

    # Category/author affinity from high-score books
    cat_affinity:    dict[str, float] = defaultdict(float)
    author_affinity: dict[str, float] = defaultdict(float)
    for bid, score in book_scores.items():
        book = catalog_client.get_product_by_id(bid)
        if not book:
            continue
        if book.get("category"):
            cat_affinity[book["category"]] += score
        if book.get("author"):
            author_affinity[book["author"]] += score

    top_cats    = {c for c, _ in sorted(cat_affinity.items(), key=lambda x: x[1], reverse=True)[:3]}
    top_authors = {a for a, _ in sorted(author_affinity.items(), key=lambda x: x[1], reverse=True)[:3]}
    if not top_cats and profile_pref_cats:
        top_cats = set(list(profile_pref_cats)[:3])

    # Fetch all products
    all_books = catalog_client.get_all_products(limit=500)
    if not all_books:
        return []

    product_ids = [b["id"] for b in all_books if b.get("id")]
    ratings     = _rating_map(product_ids)

    # Graph scores (Neo4j collaborative filtering) — w2
    graph_scores: dict[int, float] = {}
    if customer_id and neo4j_adapter.is_available():
        try:
            graph_scores = neo4j_adapter.get_graph_scores(customer_id, product_ids)
            # Normalize graph scores to [0, 1]
            max_g = max(graph_scores.values()) if graph_scores else 1.0
            if max_g > 0:
                graph_scores = {pid: s / max_g for pid, s in graph_scores.items()}
        except Exception as exc:
            logger.debug("Graph scores unavailable: %s", exc)

    candidates: list[dict] = []
    segment_boost = {
        "new": 0.95, "casual": 1.0, "engaged": 1.06, "loyal": 1.1, "champion": 1.12,
    }
    for book in all_books:
        bid = book.get("id")
        if not bid or bid in purchased or book.get("stock", 0) <= 0:
            continue

        if bid in customer_ratings:
            if customer_ratings[bid] < 3:
                continue

        price = float(book.get("price", 0))
        if budget_min is not None and price < budget_min:
            continue
        if budget_max is not None and price > budget_max:
            continue
        if category and not _matches_category(book, category):
            continue

        reasons = []

        # ── w1: LSTM behavior score ───────────────────────────────────────────
        bscore = book_scores.get(bid, 0)
        lstm_component = 0.0
        if bscore >= PURCHASE_THRESHOLD:
            lstm_component = min(bscore / 20.0, 1.0)
            reasons.append(f"bạn đã tương tác {int(bscore)} lần")
        # Boost highly-rated by customer
        if bid in customer_ratings and customer_ratings[bid] >= 4:
            lstm_component += 0.3
            reasons.append(f"bạn đánh giá cao ⭐{customer_ratings[bid]}")
        # Propensity boost
        lstm_component *= (1.0 + max(0.0, min(propensity, 1.0)) * 0.25)

        # ── w2: Graph score (Neo4j collaborative) ─────────────────────────────
        graph_component = graph_scores.get(bid, 0.0)
        if graph_component > 0:
            reasons.append("khách hàng tương tự cũng quan tâm")

        # ── w3: Content affinity ──────────────────────────────────────────────
        content_component = 0.0
        if book.get("category") in top_cats:
            content_component += 0.6
            reasons.append(f"thể loại {book['category']} bạn yêu thích")
        elif book.get("category") in profile_pref_cats:
            content_component += 0.35
        if book.get("author") in top_authors:
            content_component += 0.4
            reasons.append(f"tác giả {book['author']} bạn quan tâm")

        # ── w4: Rating popularity ─────────────────────────────────────────────
        pop = _popularity_score(bid, ratings)
        rm  = ratings.get(bid, {})
        if rm.get("avg", 0) >= 4.0:
            reasons.append(f"đánh giá cao ({rm['avg']:.1f}★/{rm['count']} lượt)")

        # ── Hybrid final score ────────────────────────────────────────────────
        final_score = (
            W_LSTM    * lstm_component +
            W_GRAPH   * graph_component +
            W_CONTENT * content_component +
            W_RATING  * pop
        )
        final_score *= segment_boost.get(segment, 1.0)

        if final_score > 0 or not reasons:
            candidates.append({
                "product_id":       bid,
                "title":            book.get("title", ""),
                "author":           book.get("author", ""),
                "brand":            book.get("brand", ""),
                "category":         book.get("category", ""),
                "stock":            int(book.get("stock", 0) or 0),
                "price":            price,
                "score":            round(final_score, 3),
                "lstm_score":       round(lstm_component, 3),
                "graph_score":      round(graph_component, 3),
                "content_score":    round(content_component, 3),
                "rating_score":     round(pop, 3),
                "reason":           ", ".join(reasons) if reasons else "phổ biến trong cộng đồng",
                "avg_rating":       round(rm.get("avg", 0), 2),
            })

    candidates.sort(key=lambda x: x["score"], reverse=True)
    logger.info("Generated %d recommendations for C%s", min(len(candidates), limit), customer_id)
    return candidates[:limit]


def get_similar(
    product_id: int, 
    limit: int = 6,
    customer_ratings: dict[int, int] | None = None,  # {book_id: rating_value}
) -> list[dict[str, Any]]:
    """
    Content-based similar products.
    Similarity = same category + author + price range proximity.
    
    Applies customer rating filtering:
      - Exclude books rated < 3⭐
      - Boost books rated >= 4⭐
    """
    customer_ratings = customer_ratings or {}
    target = catalog_client.get_product_by_id(product_id)
    if not target:
        return []

    all_books = catalog_client.get_all_products(limit=500)
    product_ids = [b["id"] for b in all_books if b.get("id")]
    ratings = _rating_map(product_ids)

    target_cat    = target.get("category", "")
    target_author = target.get("author", "")
    target_price  = float(target.get("price", 0))

    candidates = []
    for book in all_books:
        bid = book.get("id")
        if not bid or bid == product_id or book.get("stock", 0) <= 0:
            continue

        # Filter: exclude books customer rated poorly (< 3⭐)
        if bid in customer_ratings:
            cust_rating = customer_ratings[bid]
            if cust_rating < 3:
                continue

        score   = 0.0
        reasons = []

        if book.get("category") == target_cat:
            score += 3.0
            reasons.append(f"cùng thể loại {target_cat}")
        if book.get("author") == target_author and target_author:
            score += 2.5
            reasons.append(f"cùng tác giả {target_author}")

        price = float(book.get("price", 0))
        if target_price > 0:
            price_diff = abs(price - target_price) / target_price
            if price_diff < 0.3:
                score += 1.0
                reasons.append("tầm giá tương đương")

        # Boost: prioritize books customer rated highly (>= 4⭐)
        if bid in customer_ratings:
            cust_rating = customer_ratings[bid]
            if cust_rating >= 4:
                score += 3.5
                reasons.append(f"bạn đánh giá cao ⭐{cust_rating}")

        pop = _popularity_score(bid, ratings)
        score += pop

        if score > 0:
            rm = ratings.get(bid, {})
            candidates.append({
                "product_id": bid,
                "title":      book.get("title", ""),
                "author":     book.get("author", ""),
                "brand":      book.get("brand", ""),
                "category":   book.get("category", ""),
                "stock":      int(book.get("stock", 0) or 0),
                "price":      price,
                "score":      round(score, 3),
                "reason":     ", ".join(reasons) if reasons else "sản phẩm tương tự",
                "avg_rating": round(rm.get("avg", 0), 2),
            })

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:limit]


def get_popular(limit: int = 10) -> list[dict[str, Any]]:
    """Global popularity based on ratings."""
    all_books = catalog_client.get_all_products(limit=500)
    product_ids = [b["id"] for b in all_books if b.get("id")]
    ratings = _rating_map(product_ids)

    result = []
    for book in all_books:
        bid = book.get("id")
        if not bid or book.get("stock", 0) <= 0:
            continue
        rm    = ratings.get(bid, {})
        score = _popularity_score(bid, ratings)
        if score > 0 or rm.get("count", 0) > 0:
            result.append({
                "product_id": bid,
                "title":      book.get("title", ""),
                "author":     book.get("author", ""),
                "brand":      book.get("brand", ""),
                "category":   book.get("category", ""),
                "stock":      int(book.get("stock", 0) or 0),
                "price":      float(book.get("price", 0)),
                "score":      round(score, 3),
                "reason":     f"phổ biến ({rm.get('count', 0)} đánh giá)",
                "avg_rating": round(rm.get("avg", 0), 2),
            })

    result.sort(key=lambda x: x["score"], reverse=True)
    return result[:limit]


recommendation_service = type("RecService", (), {
    "get_personalized": staticmethod(get_personalized),
    "get_similar":      staticmethod(get_similar),
    "get_popular":      staticmethod(get_popular),
})()
