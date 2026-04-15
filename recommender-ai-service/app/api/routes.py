"""FastAPI routers for AI Assistant Service."""
from __future__ import annotations
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from .schemas import (
    ChatRequest, ChatResponse,
    RecommendationResponse, RecommendationItem,
    SimilarProductResponse,
    BehaviorProfile,
    KBStatusResponse, KBReindexResponse,
    TrackRequest,
)
from ..orchestrator import orchestrator
from ..services.recommendation   import recommendation_service as rec_svc
from ..services.behavior_analysis import behavior_service
from ..services.kb_ingestion     import kb_service
from ..services.rag_retrieval    import rag_service

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/health", tags=["system"])
def health():
    stats = kb_service.get_stats()
    return {
        "service": "moonbooks-ai-assistant",
        "status":  "healthy",
        "modules": ["intent_detector", "entity_extractor", "behavior_analysis",
                    "recommendation", "kb_ingestion", "rag_retrieval",
                    "order_support", "response_composer", "orchestrator"],
        "kb_stats": stats,
    }


# ── Chat ──────────────────────────────────────────────────────────────────────

@router.post("/api/v1/chat", response_model=ChatResponse, tags=["chat"])
def chat(req: ChatRequest):
    """
    Main chatbot endpoint.
    Supports all intents: faq, product_advice, order_support,
    payment_support, shipping_support, return_policy, general_search, fallback.
    """
    try:
        result = orchestrator.process(
            message=req.message,
            customer_id=req.customer_id,
            session_id=req.session_id,
            quick_action=req.quick_action,
        )
        return ChatResponse(**result)
    except Exception as exc:
        logger.exception("Chat error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── Recommendations ───────────────────────────────────────────────────────────

@router.get("/api/v1/recommend/{customer_id}", response_model=RecommendationResponse, tags=["recommend"])
def recommend(
    customer_id: int,
    limit:       int   = Query(8, ge=1, le=20),
    category:    Optional[str]  = None,
    budget_max:  Optional[float] = None,
):
    """Personalized recommendations for a customer."""
    try:
        # Load interactions from DB
        interactions: dict = {}
        try:
            from django.apps import apps
            CustomerBookInteraction = apps.get_model("app", "CustomerBookInteraction")
            qs = CustomerBookInteraction.objects.filter(customer_id=customer_id)
            for ix in qs:
                interactions.setdefault(ix.interaction_type, {})[ix.book_id] = ix.count
        except Exception:
            pass

        recs = rec_svc.get_personalized(
            customer_id=customer_id,
            interactions=interactions,
            limit=limit,
            category=category,
            budget_max=budget_max,
        )
        if not recs:
            recs = rec_svc.get_popular(limit=limit)

        items = [RecommendationItem(**r) for r in recs]
        return RecommendationResponse(
            customer_id=customer_id,
            recommendations=items,
            source="personalized" if interactions else "popular",
        )
    except Exception as exc:
        logger.exception("Recommend error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/api/v1/recommend/similar/{product_id}", response_model=SimilarProductResponse, tags=["recommend"])
def similar(product_id: int, limit: int = Query(6, ge=1, le=12)):
    """Similar products based on content-based filtering."""
    try:
        items = rec_svc.get_similar(product_id, limit=limit)
        return SimilarProductResponse(
            product_id=product_id,
            similar=[RecommendationItem(**i) for i in items],
        )
    except Exception as exc:
        logger.exception("Similar error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── Behavior Analysis ─────────────────────────────────────────────────────────

@router.get("/api/v1/analyze-customer/{customer_id}", response_model=BehaviorProfile, tags=["behavior"])
def analyze_customer(customer_id: int):
    """Deep behavior analysis for a customer."""
    try:
        interactions: dict[str, int] = {}
        try:
            from django.apps import apps
            CustomerBookInteraction = apps.get_model("app", "CustomerBookInteraction")
            qs = CustomerBookInteraction.objects.filter(customer_id=customer_id)
            for ix in qs:
                interactions[ix.interaction_type] = interactions.get(ix.interaction_type, 0) + ix.count
        except Exception:
            pass

        profile = behavior_service.analyze(customer_id, interactions)
        return BehaviorProfile(**profile)
    except Exception as exc:
        logger.exception("Analyze error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── Interaction Tracking ──────────────────────────────────────────────────────

@router.post("/api/v1/track", tags=["behavior"])
def track_interaction(req: TrackRequest):
    """Track a customer interaction (view/search/cart/purchase/rate)."""
    try:
        import django, os
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "recommender_ai_service.settings")
        try:
            django.setup()
        except RuntimeError:
            pass  # already set up
        from django.apps import apps
        CustomerBookInteraction = apps.get_model("app", "CustomerBookInteraction")

        product_id = req.product_id
        if product_id is None:
            if req.interaction_type == "search":
                # Keep global search behavior even when no concrete product is clicked.
                product_id = 0
            else:
                raise HTTPException(status_code=422, detail="product_id is required for this interaction_type")

        obj, created = CustomerBookInteraction.objects.get_or_create(
            customer_id=req.customer_id,
            book_id=product_id,
            interaction_type=req.interaction_type,
            defaults={"count": 1, "rating": req.rating},
        )
        if not created:
            obj.count += 1
            if req.rating is not None:
                obj.rating = req.rating
            obj.save(update_fields=["count", "rating", "timestamp"])
        return {
            "customer_id":      req.customer_id,
            "product_id":       product_id,
            "interaction_type": req.interaction_type,
            "query":            req.query,
            "count":            obj.count,
            "created":          created,
        }
    except Exception as exc:
        logger.exception("Track error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── Knowledge Base ────────────────────────────────────────────────────────────

@router.post("/api/v1/kb/reindex", response_model=KBReindexResponse, tags=["kb"])
def kb_reindex():
    """Reindex the Knowledge Base from all sources."""
    try:
        count = kb_service.reindex()
        indexed = rag_service.build_index()
        return KBReindexResponse(
            indexed=indexed,
            message=f"KB reindexed: {count} entries, FAISS indexed: {indexed} vectors",
        )
    except Exception as exc:
        logger.exception("KB reindex error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/api/v1/kb/status", response_model=KBStatusResponse, tags=["kb"])
def kb_status():
    """Knowledge Base status."""
    from ..core.config import FAISS_INDEX_PATH
    stats = kb_service.get_stats()
    return KBStatusResponse(
        total_entries=stats["total_entries"],
        by_category=stats["by_category"],
        faiss_indexed=FAISS_INDEX_PATH.exists(),
        index_size=stats["total_entries"],
    )
