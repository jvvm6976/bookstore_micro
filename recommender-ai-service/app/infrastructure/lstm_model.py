from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

import torch
import torch.nn as nn

from ..core.config import MODEL_PATH
from ..clients.catalog_client import catalog_client

logger = logging.getLogger(__name__)


class SequenceLSTM(nn.Module):
    def __init__(self, input_dim: int = 8, hidden_dim: int = 32):
        super().__init__()
        self.lstm = nn.LSTM(input_dim, hidden_dim, batch_first=True)
        self.head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 1),
            nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        output, _ = self.lstm(x)
        return self.head(output[:, -1, :]).squeeze(-1)


def _book_category_key(book: dict) -> str:
    category_detail = book.get("category_detail")
    if isinstance(category_detail, dict):
        return str(category_detail.get("slug") or category_detail.get("name") or book.get("category") or "")
    return str(book.get("category") or "")


class LstmRanker:
    def __init__(self):
        self.model: SequenceLSTM | None = None
        self._load()

    def _load(self) -> None:
        if not MODEL_PATH.exists():
            logger.info("No LSTM checkpoint found at %s; using heuristic sequence scorer", MODEL_PATH)
            return
        try:
            self.model = SequenceLSTM()
            self.model.load_state_dict(torch.load(str(MODEL_PATH), map_location="cpu"))
            self.model.eval()
            logger.info("Loaded LSTM checkpoint from %s", MODEL_PATH)
        except Exception as exc:
            logger.warning("Could not load LSTM checkpoint: %s", exc)
            self.model = None

    def score_candidates(self, customer_id: int, interactions: dict[str, dict[int, int]], candidate_products: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
        recent_books: list[int] = []
        for book_counts in interactions.values():
            recent_books.extend(list(book_counts.keys()))

        recent_meta = []
        for book_id in recent_books[-12:]:
            book = catalog_client.get_product_by_id(book_id)
            if book:
                recent_meta.append(book)

        cat_scores = defaultdict(float)
        brand_scores = defaultdict(float)
        type_scores = defaultdict(float)
        for idx, book in enumerate(reversed(recent_meta), start=1):
            weight = 1.0 / idx
            cat_scores[_book_category_key(book)] += weight
            brand_scores[str(book.get("brand_detail", {}).get("slug") if isinstance(book.get("brand_detail"), dict) else book.get("brand") or "")] += weight
            type_scores[str(book.get("type_detail", {}).get("slug") if isinstance(book.get("type_detail"), dict) else book.get("product_type") or "")] += weight

        results: dict[int, dict[str, Any]] = {}
        for book in candidate_products:
            pid = int(book.get("id") or 0)
            if not pid:
                continue
            category = _book_category_key(book)
            brand = str(book.get("brand_detail", {}).get("slug") if isinstance(book.get("brand_detail"), dict) else book.get("brand") or "")
            product_type = str(book.get("type_detail", {}).get("slug") if isinstance(book.get("type_detail"), dict) else book.get("product_type") or "")

            heuristic_score = 0.0
            reasons = []
            if category and cat_scores.get(category, 0):
                heuristic_score += cat_scores[category] * 1.8
                reasons.append(f"chuỗi hành vi gần đây ưu tiên {category}")
            if brand and brand_scores.get(brand, 0):
                heuristic_score += brand_scores[brand] * 1.1
                reasons.append(f"thương hiệu {brand} xuất hiện trong lịch sử gần đây")
            if product_type and type_scores.get(product_type, 0):
                heuristic_score += type_scores[product_type] * 1.0
                reasons.append(f"loại sản phẩm {product_type} phù hợp với chuỗi xem gần đây")

            results[pid] = {
                "score": round(heuristic_score, 3),
                "reason": "; ".join(reasons) if reasons else "mẫu chuỗi hành vi bổ trợ",
            }

        return results


lstm_ranker = LstmRanker()
