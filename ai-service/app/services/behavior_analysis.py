"""
BehaviorAnalysisService
────────────────────────
Pipeline:
  1. LSTM (PyTorch) — primary model, sequence-based (bám sát yêu cầu môn)
  2. MLP (PyTorch)  — fallback nếu không có LSTM checkpoint
  3. Rule-based     — fallback cuối cùng

Feature vector cho LSTM: chuỗi sự kiện {product_id, interaction_type, timestamp, price_range, category_idx}
Feature vector cho MLP:  [views, searches, cart, purchases, ratings, avg_rating, unique_cats, avg_price, days_since, purchase_freq]
"""
from __future__ import annotations
import logging
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import torch
import torch.nn as nn

from ..core.config import MODEL_PATH, PURCHASE_THRESHOLD
from ..clients.order_client import order_client
from ..clients.comment_client import comment_client
from ..clients.catalog_client import catalog_client
from ..infrastructure.ml import lstm_model as lstm_mod

logger = logging.getLogger(__name__)

FEATURE_DIM = 10
SEGMENTS    = ["new", "casual", "engaged", "loyal", "champion"]
WEIGHTS     = {"view": 1, "search": 2, "cart": 4, "purchase": 8, "rate": 3}


# ── MLP fallback model ────────────────────────────────────────────────────────

class BehaviorMLP(nn.Module):
    """MLP fallback — dùng khi không có LSTM checkpoint."""
    def __init__(self, feature_dim: int = FEATURE_DIM, hidden: int = 32, n_segments: int = 5):
        super().__init__()
        self.shared = nn.Sequential(
            nn.Linear(feature_dim, hidden), nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(hidden, hidden // 2), nn.ReLU(),
        )
        self.engagement_head = nn.Sequential(nn.Linear(hidden // 2, 1), nn.Sigmoid())
        self.propensity_head = nn.Sequential(nn.Linear(hidden // 2, 1), nn.Sigmoid())
        self.segment_head    = nn.Linear(hidden // 2, n_segments)

    def forward(self, x: torch.Tensor):
        h = self.shared(x)
        return (
            self.engagement_head(h).squeeze(-1),
            self.propensity_head(h).squeeze(-1),
            self.segment_head(h),
        )


# ── Feature builder for MLP ───────────────────────────────────────────────────

def _build_mlp_features(
    interactions: dict[str, int],
    orders: list[dict],
    ratings: list[dict],
    all_products: list[dict],
) -> list[float]:
    product_map = {p["id"]: p for p in all_products if p.get("id")}

    total_views     = interactions.get("view", 0)
    total_searches  = interactions.get("search", 0)
    total_cart      = interactions.get("cart", 0)
    total_purchases = len(orders)
    total_ratings   = len(ratings)
    avg_rating      = (sum(r.get("rating", 0) for r in ratings) / total_ratings) if total_ratings else 0.0

    cats: set[str] = set()
    prices: list[float] = []
    for order in orders:
        for item in order.get("items", []):
            pid = item.get("product_id") or item.get("book_id")
            if pid and pid in product_map:
                cat = product_map[pid].get("category") or product_map[pid].get("category_slug")
                if cat:
                    cats.add(cat)
                price = float(product_map[pid].get("price", 0))
                if price > 0:
                    prices.append(price)

    avg_price_norm = min((sum(prices) / len(prices) if prices else 0.0) / 1_000_000, 1.0)
    days_since     = max(0, 30 - total_purchases * 3)

    return [
        min(total_views     / 50.0, 1.0),
        min(total_searches  / 20.0, 1.0),
        min(total_cart      / 10.0, 1.0),
        min(total_purchases / 10.0, 1.0),
        min(total_ratings   / 10.0, 1.0),
        avg_rating / 5.0,
        min(len(cats) / 5.0, 1.0),
        avg_price_norm,
        min(days_since / 30.0, 1.0),
        min(total_purchases / 10.0, 1.0),
    ]


# ── Rule-based fallback ───────────────────────────────────────────────────────

def _rule_based_profile(
    customer_id: int,
    interactions: dict[str, int],
    orders: list[dict],
    ratings: list[dict],
    all_products: list[dict],
) -> dict[str, Any]:
    product_map = {p["id"]: p for p in all_products if p.get("id")}

    total_score     = sum(WEIGHTS.get(k, 1) * v for k, v in interactions.items())
    total_purchases = len(orders)

    cat_scores: dict[str, float] = defaultdict(float)
    prices: list[float] = []

    for order in orders:
        for item in order.get("items", []):
            pid = item.get("product_id") or item.get("book_id")
            if pid and pid in product_map:
                cat = product_map[pid].get("category") or product_map[pid].get("category_slug", "")
                if cat:
                    cat_scores[cat] += 8.0
                price = float(product_map[pid].get("price", 0))
                if price > 0:
                    prices.append(price)

    for r in ratings:
        pid = r.get("product_id") or r.get("book_id")
        if pid and pid in product_map:
            cat = product_map[pid].get("category") or product_map[pid].get("category_slug", "")
            if cat:
                cat_scores[cat] += float(r.get("rating", 3)) * 0.5

    preferred_categories = sorted(
        [{"category": c, "score": round(s, 2)} for c, s in cat_scores.items()],
        key=lambda x: x["score"], reverse=True
    )[:5]

    price_min = min(prices) if prices else 0.0
    price_max = max(prices) if prices else 500_000.0
    price_avg = sum(prices) / len(prices) if prices else 150_000.0

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

    top_reasons = []
    if preferred_categories:
        top_reasons.append(f"Quan tâm thể loại: {preferred_categories[0]['category']}")
    if total_purchases > 0:
        top_reasons.append(f"Đã mua {total_purchases} đơn hàng")
    if prices:
        top_reasons.append(f"Tầm giá thường mua: {int(price_avg):,}đ")

    return {
        "customer_id":               customer_id,
        "preferred_categories":      preferred_categories,
        "preferred_price_range":     {"min": price_min, "max": price_max, "avg": price_avg},
        "engagement_score":          round(min(total_score / 50.0, 1.0), 3),
        "purchase_propensity_score": round(min(total_purchases / 10.0, 1.0), 3),
        "customer_segment":          segment,
        "top_reasons":               top_reasons,
        "model_source":              "rule_based",
    }


# ── Main service ──────────────────────────────────────────────────────────────

class BehaviorAnalysisService:
    """
    Behavior analysis service.
    Priority: LSTM (PyTorch) > MLP (PyTorch) > Rule-based
    """
    def __init__(self):
        self._mlp: BehaviorMLP | None = None
        self._load_mlp()

    def _load_mlp(self) -> None:
        if MODEL_PATH.exists():
            try:
                self._mlp = BehaviorMLP()
                self._mlp.load_state_dict(torch.load(str(MODEL_PATH), map_location="cpu"))
                self._mlp.eval()
                logger.info("MLP fallback model loaded from %s", MODEL_PATH)
            except Exception as exc:
                logger.warning("Could not load MLP model: %s", exc)
                self._mlp = None

    def analyze(
        self,
        customer_id: int,
        interactions: dict[str, int] | None = None,
        event_sequence: list[dict] | None = None,
    ) -> dict[str, Any]:
        """
        Build behavior profile.
        interactions: {interaction_type: count}
        event_sequence: list of {product_id, interaction_type, timestamp, price_range, category_idx}
        """
        if interactions is None:
            interactions = {}

        orders   = order_client.get_orders_by_customer(customer_id)
        comments = comment_client.get_all_comments()
        ratings  = [c for c in comments if c.get("customer_id") == customer_id]
        products = catalog_client.get_all_products(limit=500)

        # 1. LSTM — primary model (sequence-based, bám sát yêu cầu môn)
        if event_sequence:
            lstm_result = lstm_mod.predict(event_sequence)
            if lstm_result is not None:
                base = _rule_based_profile(customer_id, interactions, orders, ratings, products)
                base.update({
                    "engagement_score":          lstm_result["engagement_score"],
                    "purchase_propensity_score": lstm_result["purchase_propensity"],
                    "customer_segment":          lstm_result["customer_segment"],
                    "model_source":              lstm_result["model_source"],
                })
                return base

        # 2. MLP fallback
        if self._mlp is not None:
            return self._mlp_profile(customer_id, interactions, orders, ratings, products)

        # 3. Rule-based fallback
        return _rule_based_profile(customer_id, interactions, orders, ratings, products)

    def _mlp_profile(
        self,
        customer_id: int,
        interactions: dict[str, int],
        orders: list[dict],
        ratings: list[dict],
        products: list[dict],
    ) -> dict[str, Any]:
        features = _build_mlp_features(interactions, orders, ratings, products)
        x = torch.tensor([features], dtype=torch.float32)
        with torch.no_grad():
            eng, prop, seg_logits = self._mlp(x)
        seg_idx = int(seg_logits.argmax(dim=-1).item())
        segment = SEGMENTS[seg_idx] if seg_idx < len(SEGMENTS) else "casual"

        base = _rule_based_profile(customer_id, interactions, orders, ratings, products)
        base.update({
            "engagement_score":          round(float(eng.item()), 3),
            "purchase_propensity_score": round(float(prop.item()), 3),
            "customer_segment":          segment,
            "model_source":              "pytorch_mlp",
        })
        return base


behavior_service = BehaviorAnalysisService()
