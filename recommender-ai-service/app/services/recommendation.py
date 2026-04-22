"""
RecommendationService
──────────────────────
Personalized recommendations combining:
  1. Behavior scores (interaction history)
  2. Content-based filtering (category/author affinity)
  3. Collaborative signals (rating popularity)
  4. Budget filtering

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

logger = logging.getLogger(__name__)

WEIGHTS = {
    "view": 1,
    "search": 2,
    "cart": 4,
    "purchase": 8,
    "rate": 3,
    "click_detail_button": 2,
    "click_wishlist_button": 3,
    "click": 2,
    "add_to_cart": 4,
    "remove_from_cart": 1,
    "add_to_wishlist": 3,
    "remove_from_wishlist": 1,
    "checkout": 6,
}


def _book_category_key(book: dict) -> str | None:
    category_detail = book.get("category_detail")
    if isinstance(category_detail, dict):
        slug = category_detail.get("slug")
        if slug:
            return str(slug)
        name = category_detail.get("name")
        if name:
            return str(name)

    category = book.get("category")
    if category is None:
        return None
    return str(category)


def _book_title(book: dict) -> str:
    return str(book.get("title") or book.get("name") or "")


def _get_purchased_ids(customer_id: int) -> set[int]:
    orders = order_client.get_orders_by_customer(customer_id)
    ids: set[int] = set()
    for order in orders:
        for item in order.get("items", []):
            if item.get("book_id"):
                ids.add(item["book_id"])
    return ids


def _rating_map(product_ids: list[int]) -> dict[int, dict]:
    return comment_client.get_reviews_for_products(product_ids)


def _popularity_score(book_id: int, ratings: dict[int, dict]) -> float:
    rm = ratings.get(book_id, {})
    if not rm.get("count", 0):
        return 0.0
    return (rm["avg"] / 5.0) * math.log1p(rm["count"]) * 0.3


def get_personalized(
    customer_id: int,
    interactions: dict[str, dict[int, int]],   # {type: {book_id: count}}
    limit: int = RECOMMENDATION_LIMIT,
    budget_min: float | None = None,
    budget_max: float | None = None,
    category: str | None = None,
    brand: str | None = None,
    product_type: str | None = None,
    customer_ratings: dict[int, int] | None = None,  # {book_id: rating_value}
) -> list[dict[str, Any]]:
    """
    Generate personalized recommendations.
    interactions: {interaction_type: {book_id: count}}
    customer_ratings: {book_id: rating_value} - customer's own historical ratings
    
    Filter logic:
      - Exclude books rated < 3⭐ (bad experience)
      - Boost books rated >= 4⭐ (highly recommend)
    """
    customer_ratings = customer_ratings or {}
    # Flatten to {book_id: weighted_score}
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
        profile = behavior_service.analyze(customer_id, interaction_totals)
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
        category_key = _book_category_key(book)
        if category_key:
            cat_affinity[category_key] += score
        if book.get("author"):
            author_affinity[book["author"]] += score

    top_cats    = {c for c, _ in sorted(cat_affinity.items(), key=lambda x: x[1], reverse=True)[:3]}
    top_authors = {a for a, _ in sorted(author_affinity.items(), key=lambda x: x[1], reverse=True)[:3]}
    profile_pref_cats = set(profile_pref_cats)
    if not top_cats and profile_pref_cats:
        top_cats = set(list(profile_pref_cats)[:3])

    # Fetch all books
    all_books = catalog_client.get_all_products(limit=500)
    if not all_books:
        return []

    product_ids = [b["id"] for b in all_books if b.get("id")]
    ratings     = _rating_map(product_ids)

    candidates: list[dict] = []
    segment_boost = {
        "new": 0.95,
        "casual": 1.0,
        "engaged": 1.06,
        "loyal": 1.1,
        "champion": 1.12,
    }
    for book in all_books:
        bid = book.get("id")
        if not bid or bid in purchased or book.get("stock", 0) <= 0:
            continue

        book_category = _book_category_key(book)

        # Filter: exclude books customer rated poorly (< 3⭐)
        if bid in customer_ratings:
            cust_rating = customer_ratings[bid]
            if cust_rating < 3:
                logger.debug("Excluding B%s for C%s (low rating: %d⭐)", bid, customer_id, cust_rating)
                continue

        price = float(book.get("price", 0))
        if budget_min is not None and price < budget_min:
            continue
        if budget_max is not None and price > budget_max:
            continue
        if category and book_category != category:
            continue
        if product_type and str(book.get("product_type") or book.get("type_detail", {}).get("slug") if isinstance(book.get("type_detail"), dict) else book.get("product_type") or "") != product_type:
            continue
        if brand and str(book.get("brand") or book.get("brand_detail", {}).get("slug") if isinstance(book.get("brand_detail"), dict) else book.get("brand") or "") != brand:
            continue

        score   = 0.0
        reasons = []

        # Direct behavior signal
        bscore = book_scores.get(bid, 0)
        if bscore >= PURCHASE_THRESHOLD:
            score += bscore * 0.4
            reasons.append(f"bạn đã tương tác {int(bscore)} lần")

        # Boost: prioritize books customer rated highly (>= 4⭐)
        if bid in customer_ratings:
            cust_rating = customer_ratings[bid]
            if cust_rating >= 4:
                score += 5.0
                reasons.append(f"bạn đã đánh giá cao ⭐{cust_rating} trước đây")

        # Category match
        if book_category in top_cats:
            score += 3.0
            reasons.append(f"thể loại {book_category} bạn yêu thích")
        elif book_category in profile_pref_cats:
            score += 2.2
            reasons.append(f"phù hợp hồ sơ sở thích thể loại của bạn")

        book_type = str(book.get("product_type") or book.get("type_detail", {}).get("slug") if isinstance(book.get("type_detail"), dict) else book.get("product_type") or "")
        book_brand = str(book.get("brand") or book.get("brand_detail", {}).get("slug") if isinstance(book.get("brand_detail"), dict) else book.get("brand") or "")
        if product_type and book_type == product_type:
            score += 2.4
            reasons.append(f"đúng loại sản phẩm {product_type}")
        if brand and book_brand == brand:
            score += 2.4
            reasons.append(f"cùng thương hiệu {brand}")

        # Author match
        if book.get("author") in top_authors:
            score += 1.5
            reasons.append(f"tác giả {book['author']} bạn quan tâm")

        # Popularity
        pop = _popularity_score(bid, ratings)
        score += pop
        rm = ratings.get(bid, {})
        if rm.get("avg", 0) >= 4.0:
            reasons.append(f"đánh giá cao ({rm['avg']:.1f}★/{rm['count']} lượt)")

        # Calibrate score by per-customer behavior profile.
        score *= (1.0 + max(0.0, min(propensity, 1.0)) * 0.35)
        score *= segment_boost.get(segment, 1.0)

        if profile_pref_cats and book_category in profile_pref_cats:
            score += 1.0

        if score > 0 or not reasons:
            candidates.append({
                "product_id": bid,
                "title":      _book_title(book),
                "author":     book.get("author", ""),
                "category":   book_category or "",
                "price":      price,
                "score":      round(score, 3),
                "reason":     ", ".join(reasons) if reasons else "phổ biến trong cộng đồng",
                "avg_rating": round(rm.get("avg", 0), 2),
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

    target_cat    = _book_category_key(target) or ""
    target_author = target.get("author", "")
    target_price  = float(target.get("price", 0))

    candidates = []
    for book in all_books:
        bid = book.get("id")
        if not bid or bid == product_id or book.get("stock", 0) <= 0:
            continue

        book_category = _book_category_key(book)

        # Filter: exclude books customer rated poorly (< 3⭐)
        if bid in customer_ratings:
            cust_rating = customer_ratings[bid]
            if cust_rating < 3:
                continue

        score   = 0.0
        reasons = []

        if book_category == target_cat:
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
                "title":      _book_title(book),
                "author":     book.get("author", ""),
                "category":   book_category or "",
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
        book_category = _book_category_key(book)
        rm    = ratings.get(bid, {})
        score = _popularity_score(bid, ratings)
        if score > 0 or rm.get("count", 0) > 0:
            result.append({
                "product_id": bid,
                "title":      _book_title(book),
                "author":     book.get("author", ""),
                "category":   book_category or "",
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
