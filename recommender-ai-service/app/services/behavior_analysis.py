"""
BehaviorAnalysisService
────────────────────────
Deep Learning model (PyTorch) for customer behavior analysis.

Architecture: simple MLP that takes a feature vector and outputs
  - engagement_score
  - purchase_propensity_score
  - customer_segment (embedding index)

Feature vector (per customer):
  [0]  total_views
  [1]  total_searches
  [2]  total_cart_adds
  [3]  total_purchases
  [4]  total_ratings
  [5]  avg_rating_given
  [6]  unique_categories
  [7]  avg_price_purchased
  [8]  days_since_last_activity
  [9]  purchase_frequency

If model checkpoint not found → falls back to rule-based profile builder.
"""
from __future__ import annotations
import logging
from collections import defaultdict, Counter
from pathlib import Path
from typing import Any

import torch
import torch.nn as nn

from ..core.config import MODEL_PATH, PURCHASE_THRESHOLD
from ..clients.order_client import order_client
from ..clients.comment_client import comment_client
from ..clients.catalog_client import catalog_client

logger = logging.getLogger(__name__)

FEATURE_DIM = 10
SEGMENTS    = ["new", "casual", "engaged", "loyal", "champion"]

# ── Interaction weights ───────────────────────────────────────────────────────
WEIGHTS = {
    "view": 1,
    "search": 2,
    "cart": 4,
    "purchase": 8,
    "rate": 3,
    "click_detail_button": 2,
    "click_wishlist_button": 3,
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


# ── PyTorch Model ─────────────────────────────────────────────────────────────

class BehaviorMLP(nn.Module):
    """
    Simple MLP: feature_dim → hidden → [engagement, propensity, segment_logits]
    """
    def __init__(self, feature_dim: int = FEATURE_DIM, hidden: int = 32, n_segments: int = 5):
        super().__init__()
        self.shared = nn.Sequential(
            nn.Linear(feature_dim, hidden),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden, hidden // 2),
            nn.ReLU(),
        )
        self.engagement_head  = nn.Sequential(nn.Linear(hidden // 2, 1), nn.Sigmoid())
        self.propensity_head  = nn.Sequential(nn.Linear(hidden // 2, 1), nn.Sigmoid())
        self.segment_head     = nn.Linear(hidden // 2, n_segments)

    def forward(self, x: torch.Tensor):
        h = self.shared(x)
        return (
            self.engagement_head(h).squeeze(-1),
            self.propensity_head(h).squeeze(-1),
            self.segment_head(h),
        )


# ── Feature builder ───────────────────────────────────────────────────────────

def _build_features(
    interactions: dict[str, int],   # {interaction_type: count}
    orders: list[dict],
    ratings: list[dict],
    all_books: list[dict],
) -> list[float]:
    book_map = {b["id"]: b for b in all_books if b.get("id")}

    total_views     = interactions.get("view", 0)
    total_searches  = interactions.get("search", 0)
    total_cart      = interactions.get("cart", 0)
    total_purchases = len(orders)
    total_ratings   = len(ratings)
    avg_rating      = (sum(r.get("rating", 0) for r in ratings) / total_ratings) if total_ratings else 0.0

    # Category diversity
    cats: set[str] = set()
    prices: list[float] = []
    for order in orders:
        for item in order.get("items", []):
            bid = item.get("book_id")
            if bid and bid in book_map:
                cat = _book_category_key(book_map[bid])
                if cat:
                    cats.add(cat)
                price = float(book_map[bid].get("price", 0))
                if price > 0:
                    prices.append(price)

    avg_price = sum(prices) / len(prices) if prices else 0.0
    # Normalize avg_price to [0,1] assuming max 1_000_000 VND
    avg_price_norm = min(avg_price / 1_000_000, 1.0)

    # Days since last activity (simplified: use total_purchases as proxy)
    days_since = max(0, 30 - total_purchases * 3)
    days_norm  = min(days_since / 30.0, 1.0)

    # Purchase frequency (purchases per 30 days, capped at 1)
    purchase_freq = min(total_purchases / 10.0, 1.0)

    return [
        min(total_views    / 50.0, 1.0),
        min(total_searches / 20.0, 1.0),
        min(total_cart     / 10.0, 1.0),
        min(total_purchases / 10.0, 1.0),
        min(total_ratings  / 10.0, 1.0),
        avg_rating / 5.0,
        min(len(cats) / 5.0, 1.0),
        avg_price_norm,
        days_norm,
        purchase_freq,
    ]


# ── Rule-based fallback ───────────────────────────────────────────────────────

def _rule_based_profile(
    customer_id: int,
    interactions: dict[str, int],
    orders: list[dict],
    ratings: list[dict],
    all_books: list[dict],
) -> dict[str, Any]:
    book_map = {b["id"]: b for b in all_books if b.get("id")}

    total_score = sum(WEIGHTS.get(k, 1) * v for k, v in interactions.items())
    total_purchases = len(orders)

    # Category affinity
    cat_scores: dict[str, float] = defaultdict(float)
    prices: list[float] = []
    for order in orders:
        for item in order.get("items", []):
            bid = item.get("book_id")
            if bid and bid in book_map:
                cat = _book_category_key(book_map[bid])
                if cat:
                    cat_scores[cat] += 8.0
                price = float(book_map[bid].get("price", 0))
                if price > 0:
                    prices.append(price)

    for r in ratings:
        bid = r.get("book_id")
        if bid and bid in book_map:
            cat = _book_category_key(book_map[bid])
            if cat:
                cat_scores[cat] += float(r.get("rating", 3)) * 0.5

    preferred_categories = sorted(
        [{"category": c, "score": round(s, 2)} for c, s in cat_scores.items()],
        key=lambda x: x["score"], reverse=True
    )[:5]

    price_min = min(prices) if prices else 0.0
    price_max = max(prices) if prices else 500_000.0
    price_avg = sum(prices) / len(prices) if prices else 150_000.0

    # Segment
    if total_purchases == 0 and total_score < 2:
        segment = "new"
    elif total_purchases == 0:
        segment = "casual"
    elif total_purchases < 3:
        segment = "engaged"
    elif total_purchases < 8:
        segment = "loyal"
    else:
        segment = "champion"

    engagement  = min(total_score / 50.0, 1.0)
    propensity  = min(total_purchases / 10.0, 1.0)

    top_reasons = []
    if preferred_categories:
        top_reasons.append(f"Quan tâm thể loại: {preferred_categories[0]['category']}")
    if total_purchases > 0:
        top_reasons.append(f"Đã mua {total_purchases} đơn hàng")
    if prices:
        top_reasons.append(f"Tầm giá thường mua: {int(price_avg):,}đ")

    return {
        "customer_id":              customer_id,
        "preferred_categories":     preferred_categories,
        "preferred_price_range":    {"min": price_min, "max": price_max, "avg": price_avg},
        "engagement_score":         round(engagement, 3),
        "purchase_propensity_score": round(propensity, 3),
        "customer_segment":         segment,
        "top_reasons":              top_reasons,
        "model_source":             "rule_based",
    }


# ── Main service ──────────────────────────────────────────────────────────────

class BehaviorAnalysisService:
    def __init__(self):
        self._model: BehaviorMLP | None = None
        self._model_mtime: float | None = None
        self._load_model()

    def _load_model(self) -> None:
        if MODEL_PATH.exists():
            try:
                self._model = BehaviorMLP()
                self._model.load_state_dict(torch.load(str(MODEL_PATH), map_location="cpu"))
                self._model.eval()
                self._model_mtime = MODEL_PATH.stat().st_mtime
                logger.info("Loaded behavior model from %s", MODEL_PATH)
            except Exception as exc:
                logger.warning("Could not load model: %s — using rule-based fallback", exc)
                self._model = None
                self._model_mtime = None
        else:
            logger.info("No model checkpoint found at %s — using rule-based fallback", MODEL_PATH)

    def reload_if_updated(self, force: bool = False) -> bool:
        """Reload model when checkpoint is updated; return True if reloaded."""
        if not MODEL_PATH.exists():
            return False
        try:
            mtime = MODEL_PATH.stat().st_mtime
        except OSError:
            return False
        if not force and self._model_mtime is not None and mtime <= self._model_mtime:
            return False
        self._load_model()
        return self._model is not None

    def analyze(self, customer_id: int, interactions: dict[str, int] | None = None) -> dict[str, Any]:
        """
        Build behavior profile for a customer.
        interactions: {interaction_type: count} — from local DB or passed in.
        """
        if interactions is None:
            interactions = {}

        # Auto-pick fresh model checkpoint generated by scheduled training.
        self.reload_if_updated()

        orders  = order_client.get_orders_by_customer(customer_id)
        ratings = comment_client.get_all_comments()
        ratings = [c for c in ratings if c.get("customer_id") == customer_id]
        books   = catalog_client.get_all_products(limit=500)

        if self._model is not None:
            return self._dl_profile(customer_id, interactions, orders, ratings, books)
        return _rule_based_profile(customer_id, interactions, orders, ratings, books)

    def _dl_profile(
        self,
        customer_id: int,
        interactions: dict[str, int],
        orders: list[dict],
        ratings: list[dict],
        books: list[dict],
    ) -> dict[str, Any]:
        features = _build_features(interactions, orders, ratings, books)
        x = torch.tensor([features], dtype=torch.float32)
        with torch.no_grad():
            eng, prop, seg_logits = self._model(x)
        segment_idx = int(seg_logits.argmax(dim=-1).item())
        segment     = SEGMENTS[segment_idx] if segment_idx < len(SEGMENTS) else "casual"

        # Still compute rule-based for categories/price (DL doesn't output those)
        rule = _rule_based_profile(customer_id, interactions, orders, ratings, books)
        rule.update({
            "engagement_score":          round(float(eng.item()), 3),
            "purchase_propensity_score": round(float(prop.item()), 3),
            "customer_segment":          segment,
            "model_source":              "pytorch_mlp",
        })
        return rule


behavior_service = BehaviorAnalysisService()
