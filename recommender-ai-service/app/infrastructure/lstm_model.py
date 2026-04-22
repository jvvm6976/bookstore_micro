from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

import torch
import torch.nn as nn

from ..core.config import LSTM_MODEL_PATH
from ..clients.catalog_client import catalog_client

logger = logging.getLogger(__name__)


ACTION_TO_ID = {
    "view": 0,
    "click": 1,
    "search": 2,
    "add_to_cart": 3,
    "remove_from_cart": 4,
    "add_to_wishlist": 5,
    "remove_from_wishlist": 6,
    "checkout": 7,
    "purchase": 8,
    "rate": 9,
}

ACTION_PRIORITY = {
    "purchase": 9,
    "checkout": 8,
    "add_to_cart": 7,
    "view": 4,
    "click": 3,
    "search": 2,
}


class SequenceLSTM(nn.Module):
    def __init__(self, n_actions: int, embed_dim: int, hidden_dim: int, aux_dim: int = 4):
        super().__init__()
        self.embedding = nn.Embedding(n_actions, embed_dim)
        self.rnn = nn.LSTM(embed_dim + aux_dim, hidden_dim, batch_first=True)
        self.classifier = nn.Linear(hidden_dim, n_actions)

    def forward(self, x_actions: torch.Tensor, x_aux: torch.Tensor) -> torch.Tensor:
        emb = self.embedding(x_actions)
        inp = torch.cat([emb, x_aux], dim=-1)
        _, hidden = self.rnn(inp)
        h_n = hidden[0]
        h_last = h_n[-1]
        return self.classifier(h_last)


def _book_category_key(book: dict) -> str:
    category_detail = book.get("category_detail")
    if isinstance(category_detail, dict):
        return str(category_detail.get("slug") or category_detail.get("name") or book.get("category") or "")
    return str(book.get("category") or "")


class LstmRanker:
    def __init__(self):
        self.model: SequenceLSTM | None = None
        self._seq_len = 6
        self._load()

    def _load(self) -> None:
        if not LSTM_MODEL_PATH.exists():
            logger.info("No LSTM checkpoint found at %s; using heuristic sequence scorer", LSTM_MODEL_PATH)
            return
        try:
            checkpoint = torch.load(str(LSTM_MODEL_PATH), map_location="cpu")
            if not isinstance(checkpoint, dict):
                raise ValueError("Unsupported checkpoint format")

            embedding_w = checkpoint.get("embedding.weight")
            classifier_w = checkpoint.get("classifier.weight")
            if embedding_w is None or classifier_w is None:
                raise ValueError("Missing embedding/classifier weights")

            n_actions = int(embedding_w.shape[0])
            embed_dim = int(embedding_w.shape[1])
            hidden_dim = int(classifier_w.shape[1])

            self.model = SequenceLSTM(n_actions=n_actions, embed_dim=embed_dim, hidden_dim=hidden_dim)
            self.model.load_state_dict(checkpoint)
            self.model.eval()
            logger.info("Loaded LSTM checkpoint from %s", LSTM_MODEL_PATH)
        except Exception as exc:
            logger.warning("Could not load LSTM checkpoint: %s", exc)
            self.model = None

    def _build_sequence_tensors(self, interactions: dict[str, dict[int, int]]) -> tuple[torch.Tensor, torch.Tensor]:
        action_events: list[tuple[str, int]] = []
        for action, book_counts in interactions.items():
            cnt = int(sum(book_counts.values()) if isinstance(book_counts, dict) else 0)
            if cnt <= 0:
                continue
            action_events.append((action, cnt))

        action_events.sort(key=lambda x: ACTION_PRIORITY.get(x[0], 1), reverse=True)
        expanded: list[int] = []
        for action, cnt in action_events:
            action_id = ACTION_TO_ID.get(action)
            if action_id is None:
                continue
            expanded.extend([action_id] * min(cnt, 4))

        if not expanded:
            expanded = [ACTION_TO_ID["view"]]

        seq_actions = expanded[-self._seq_len :]
        if len(seq_actions) < self._seq_len:
            seq_actions = ([ACTION_TO_ID["view"]] * (self._seq_len - len(seq_actions))) + seq_actions

        aux_rows: list[list[float]] = []
        for idx, action_id in enumerate(seq_actions):
            t_norm = float(idx + 1) / float(self._seq_len)
            add_or_buy = 1.0 if action_id in {ACTION_TO_ID["add_to_cart"], ACTION_TO_ID["checkout"], ACTION_TO_ID["purchase"]} else 0.0
            search_or_click = 1.0 if action_id in {ACTION_TO_ID["search"], ACTION_TO_ID["click"], ACTION_TO_ID["view"]} else 0.0
            is_recent = 1.0 if idx >= (self._seq_len - 2) else 0.0
            aux_rows.append([t_norm, add_or_buy, search_or_click, is_recent])

        x_actions = torch.tensor([seq_actions], dtype=torch.long)
        x_aux = torch.tensor([aux_rows], dtype=torch.float32)
        return x_actions, x_aux

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

        model_boost = 0.0
        if self.model is not None:
            try:
                x_actions, x_aux = self._build_sequence_tensors(interactions)
                with torch.no_grad():
                    logits = self.model(x_actions, x_aux)
                    probs = torch.softmax(logits, dim=1).squeeze(0)
                    model_boost = float(
                        probs[ACTION_TO_ID["purchase"]]
                        + probs[ACTION_TO_ID["checkout"]]
                        + probs[ACTION_TO_ID["add_to_cart"]]
                    )
            except Exception as exc:
                logger.debug("LSTM inference fallback to heuristic only: %s", exc)
                model_boost = 0.0

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

            if model_boost > 0:
                heuristic_score += model_boost * 1.4
                reasons.append("điểm tăng từ mô hình LSTM đã huấn luyện")

            results[pid] = {
                "score": round(heuristic_score, 3),
                "reason": "; ".join(reasons) if reasons else "mẫu chuỗi hành vi bổ trợ",
            }

        return results


lstm_ranker = LstmRanker()
