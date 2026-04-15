"""Pydantic schemas for request/response."""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


# -- Chat ---------------------------------------------------------------------

class ChatRequest(BaseModel):
    customer_id: Optional[int] = None
    session_id: Optional[str] = None
    message: str = Field(..., min_length=1, max_length=2000)
    quick_action: Optional[str] = None  # recommend | return_policy | order_support | payment_support


class ChatResponse(BaseModel):
    session_id: str
    intent: str
    answer: str
    response: Optional[str] = None
    recommendations: list[dict] = []
    books: list[dict] = []
    sources: list[dict] = []
    meta: dict = {}


# -- Recommendation -----------------------------------------------------------

class RecommendationItem(BaseModel):
    product_id: int
    title: str
    author: Optional[str] = None
    category: Optional[str] = None
    price: float = 0.0
    score: float = 0.0
    reason: str = ""
    avg_rating: float = 0.0


class RecommendationResponse(BaseModel):
    customer_id: int
    recommendations: list[RecommendationItem]
    source: str = "generated"


class SimilarProductResponse(BaseModel):
    product_id: int
    similar: list[RecommendationItem]


# -- Behavior -----------------------------------------------------------------

class BehaviorProfile(BaseModel):
    model_config = {"protected_namespaces": ()}

    customer_id: int
    preferred_categories: list[dict] = []
    preferred_price_range: dict = {}
    engagement_score: float = 0.0
    purchase_propensity_score: float = 0.0
    customer_segment: str = "new"
    top_reasons: list[str] = []
    model_source: str = "rule_based"


# -- KB -----------------------------------------------------------------------

class KBStatusResponse(BaseModel):
    total_entries: int
    by_category: dict
    faiss_indexed: bool
    index_size: int


class KBReindexResponse(BaseModel):
    indexed: int
    message: str


# -- Interaction tracking -----------------------------------------------------

class TrackRequest(BaseModel):
    customer_id: int
    product_id: Optional[int] = None
    interaction_type: str  # view | search | cart | purchase | rate
    rating: Optional[int] = None
    query: Optional[str] = None  # for search interactions
