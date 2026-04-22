from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from django.apps import apps

from ..clients.catalog_client import catalog_client
from ..domain.entities import RecommendationCandidate
from ..services import recommendation as base_recommendation
from ..services.behavior_analysis import behavior_service
from ..services.rag_retrieval import rag_service
from ..infrastructure.lstm_model import lstm_ranker
from ..infrastructure.neo4j_store import neo4j_store

logger = logging.getLogger(__name__)


def _load_interactions(customer_id: int) -> dict[str, dict[int, int]]:
    try:
        CustomerBookInteraction = apps.get_model("app", "CustomerBookInteraction")
        qs = CustomerBookInteraction.objects.filter(customer_id=customer_id)
        result: dict[str, dict[int, int]] = {}
        for ix in qs:
            result.setdefault(ix.interaction_type, {})[ix.book_id] = ix.count
        return result
    except Exception as exc:
        logger.debug("Could not load interactions: %s", exc)
        return {}


def _load_customer_ratings(customer_id: int) -> dict[int, int]:
    try:
        CustomerBookInteraction = apps.get_model("app", "CustomerBookInteraction")
        qs = CustomerBookInteraction.objects.filter(
            customer_id=customer_id,
            interaction_type="rate",
            rating__isnull=False,
        )
        return {
            ix.book_id: int(ix.rating)
            for ix in qs
            if ix.rating is not None
        }
    except Exception as exc:
        logger.debug("Could not load ratings: %s", exc)
        return {}


def _candidate_key(item: dict[str, Any]) -> int:
    return int(item.get("product_id") or item.get("book_id") or item.get("id") or 0)


def _catalog_lookup(products: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    lookup: dict[int, dict[str, Any]] = {}
    for product in products:
        pid = int(product.get("id") or 0)
        if pid:
            lookup[pid] = product
    return lookup


def _to_candidate(item: dict[str, Any]) -> RecommendationCandidate:
    return RecommendationCandidate(
        product_id=_candidate_key(item),
        title=str(item.get("title") or item.get("name") or ""),
        author=str(item.get("author") or ""),
        category=str(item.get("category") or ""),
        price=float(item.get("price", 0) or 0),
        score=float(item.get("score", 0) or 0),
        reason=str(item.get("reason") or ""),
        avg_rating=float(item.get("avg_rating", 0) or 0),
        metadata={k: v for k, v in item.items() if k not in {"product_id", "book_id", "id", "title", "name", "author", "category", "price", "score", "reason", "avg_rating"}},
    )


def _merge_sources(sources: list[tuple[str, float, list[dict[str, Any]]]], limit: int) -> list[dict[str, Any]]:
    merged: dict[int, RecommendationCandidate] = {}
    reason_parts: dict[int, list[str]] = defaultdict(list)

    for source_name, source_weight, items in sources:
        for item in items:
            candidate = _to_candidate(item)
            if candidate.product_id <= 0:
                continue
            current = merged.get(candidate.product_id)
            if current is None:
                current = candidate
                merged[candidate.product_id] = current
            current.score += candidate.score * source_weight
            if candidate.title and not current.title:
                current.title = candidate.title
            if candidate.author and not current.author:
                current.author = candidate.author
            if candidate.category and not current.category:
                current.category = candidate.category
            if candidate.price and not current.price:
                current.price = candidate.price
            if candidate.avg_rating and not current.avg_rating:
                current.avg_rating = candidate.avg_rating
            if candidate.reason:
                reason_parts[candidate.product_id].append(f"{source_name}: {candidate.reason}")

    ranked = sorted(merged.values(), key=lambda x: x.score, reverse=True)[:limit]
    output = []
    for candidate in ranked:
        candidate.reason = "; ".join(reason_parts.get(candidate.product_id, [])) or candidate.reason or "hybrid recommendation"
        output.append({
            "product_id": candidate.product_id,
            "title": candidate.title,
            "author": candidate.author,
            "category": candidate.category,
            "price": candidate.price,
            "score": round(candidate.score, 3),
            "reason": candidate.reason,
            "avg_rating": round(candidate.avg_rating, 2),
        })
    return output


def _score_map_to_items(score_map: dict[int, dict[str, Any]], catalog_index: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for product_id, payload in score_map.items():
        product = catalog_index.get(int(product_id))
        if not product:
            continue
        items.append({
            "product_id": int(product_id),
            "title": str(product.get("title") or product.get("name") or ""),
            "author": str(product.get("author") or ""),
            "category": str(product.get("category") or product.get("category_detail", {}).get("slug") if isinstance(product.get("category_detail"), dict) else product.get("category") or ""),
            "price": float(product.get("price", 0) or 0),
            "score": float(payload.get("score", 0) or 0),
            "reason": str(payload.get("reason") or "") or "hybrid auxiliary score",
            "avg_rating": float(product.get("avg_rating", 0) or 0),
        })
    return items


def _persist(customer_id: int, recommendations: list[dict[str, Any]]) -> None:
    return None


def get_personalized(
    customer_id: int,
    interactions: dict[str, dict[int, int]] | None = None,
    limit: int = 8,
    budget_min: float | None = None,
    budget_max: float | None = None,
    category: str | None = None,
    brand: str | None = None,
    product_type: str | None = None,
    customer_ratings: dict[int, int] | None = None,
) -> list[dict[str, Any]]:
    interactions = interactions or _load_interactions(customer_id)
    customer_ratings = customer_ratings or _load_customer_ratings(customer_id)
    interaction_events = sum(
        sum(book_counts.values())
        for book_counts in interactions.values()
        if isinstance(book_counts, dict)
    )

    base_personalized = base_recommendation.get_personalized(
        customer_id=customer_id,
        interactions=interactions,
        limit=max(limit * 2, 10),
        budget_min=budget_min,
        budget_max=budget_max,
        category=category,
        brand=brand,
        product_type=product_type,
        customer_ratings=customer_ratings,
    )

    base_popular = base_recommendation.get_popular(limit=max(limit * 2, 10))

    recent_books = []
    for book_counts in interactions.values():
        recent_books.extend(list(book_counts.keys()))
    recent_books = list(dict.fromkeys(recent_books))[:8]

    all_books = catalog_client.get_all_products(limit=500)
    catalog_index = _catalog_lookup(all_books)
    neo4j_store.ensure_train_graph()
    neo4j_store.sync_customer_behavior(customer_id=customer_id, interactions=interactions)
    neo4j_store.sync_catalog(all_books)

    graph_scores = neo4j_store.score_candidates(
        customer_id=customer_id,
        seed_product_ids=recent_books,
        candidate_products=all_books,
    )

    lstm_scores = lstm_ranker.score_candidates(
        customer_id=customer_id,
        interactions=interactions,
        candidate_products=all_books,
    )

    profile = behavior_service.analyze(customer_id, {k: sum(v.values()) for k, v in interactions.items()})
    rag_entries = []
    if profile.get("preferred_categories"):
        top_category = profile["preferred_categories"][0].get("category")
        if top_category:
            rag_entries = rag_service.retrieve(f"{top_category} product recommendation", top_k=1)

    # Personalization-first weighting:
    # richer per-customer behavior history => stronger LSTM and graph influence,
    # weaker popularity fallback.
    if interaction_events >= 20:
        weights = {"behavior": 0.52, "popularity": 0.08, "graph": 0.20, "lstm": 0.40}
    elif interaction_events >= 8:
        weights = {"behavior": 0.54, "popularity": 0.12, "graph": 0.21, "lstm": 0.33}
    else:
        weights = {"behavior": 0.56, "popularity": 0.16, "graph": 0.22, "lstm": 0.24}

    merged = _merge_sources([
        ("behavior", weights["behavior"], base_personalized),
        ("popularity", weights["popularity"], base_popular),
        ("graph", weights["graph"], _score_map_to_items(graph_scores, catalog_index)),
        ("lstm", weights["lstm"], _score_map_to_items(lstm_scores, catalog_index)),
    ], limit)

    if rag_entries and merged:
        merged[0]["reason"] = f"{merged[0]['reason']} | RAG: {rag_entries[0]['title']}"

    _persist(customer_id, merged)
    logger.info("Generated %d hybrid recommendations for C%s", len(merged), customer_id)
    return merged


def get_similar(product_id: int, limit: int = 6, customer_ratings: dict[int, int] | None = None) -> list[dict[str, Any]]:
    return base_recommendation.get_similar(product_id=product_id, limit=limit, customer_ratings=customer_ratings)


def get_popular(limit: int = 10) -> list[dict[str, Any]]:
    return base_recommendation.get_popular(limit=limit)


hybrid_recommendation_service = type("HybridRecommendationService", (), {
    "get_personalized": staticmethod(get_personalized),
    "get_similar": staticmethod(get_similar),
    "get_popular": staticmethod(get_popular),
})()
