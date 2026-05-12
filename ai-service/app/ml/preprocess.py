from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch

ACTIONS = [
    "search",
    "view",
    "add_to_cart",
    "purchase",
    "rate_product",
    "wishlist",
    "remove_from_cart",
    "click",
]
ACTION_TO_ID = {a: i for i, a in enumerate(ACTIONS)}


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    if value in (None, ""):
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def load_rows(csv_path: str | Path) -> list[dict[str, Any]]:
    path = Path(csv_path)
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["user_id"] = _safe_int(row.get("user_id"))
            row["step"] = _safe_int(row.get("step"))
            row["product_id"] = _safe_int(row.get("product_id"))
            row["price"] = _safe_float(row.get("price"))
            row["rating"] = _safe_float(row.get("rating"))
            row["cart_value"] = _safe_float(row.get("cart_value"))
            row["action_type"] = str(row.get("action") or row.get("action_type") or "search")
            row["category"] = str(row.get("category") or "unknown")
            rows.append(row)
    rows.sort(key=lambda r: (r["user_id"], r["step"]))
    return rows


def build_category_vocab(rows: list[dict[str, Any]]) -> dict[str, int]:
    cats = sorted({str(r.get("category") or "unknown") for r in rows})
    return {c: i + 1 for i, c in enumerate(cats)}


def encode_event(
    row: dict[str, Any],
    category_to_id: dict[str, int],
    max_product_id: int,
    max_price: float,
    max_cart_value: float,
) -> np.ndarray:
    action_id = ACTION_TO_ID.get(str(row.get("action")), 0)
    category_id = category_to_id.get(str(row.get("category") or "unknown"), 0)
    product_norm = min(float(row.get("product_id", 0)) / max(max_product_id, 1), 1.0)
    price_norm = min(float(row.get("price", 0.0)) / max(max_price, 1.0), 1.0)
    cart_norm = min(float(row.get("cart_value", 0.0)) / max(max_cart_value, 1.0), 1.0)
    rating_norm = min(float(row.get("rating", 0.0)) / 5.0, 1.0)

    return np.array(
        [
            float(action_id),
            float(category_id),
            product_norm,
            price_norm,
            cart_norm,
            rating_norm,
        ],
        dtype=np.float32,
    )


@dataclass
class SequenceMeta:
    category_to_id: dict[str, int]
    max_product_id: int
    max_price: float
    max_cart_value: float
    seq_len: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "category_to_id": self.category_to_id,
            "max_product_id": self.max_product_id,
            "max_price": self.max_price,
            "max_cart_value": self.max_cart_value,
            "seq_len": self.seq_len,
            "feature_dim": 6,
            "num_classes": len(ACTIONS),
            "actions": ACTIONS,
        }


class BestModelPredictor:
    """Runtime predictor that loads artifacts/model_best.pt and metadata."""

    def __init__(self, artifacts_dir: str | Path) -> None:
        self.artifacts_dir = Path(artifacts_dir)
        self.meta_path = self.artifacts_dir / "model_best_meta.json"
        self.model_path = self.artifacts_dir / "model_best.pt"
        self.available = False
        self.model = None
        self.meta: dict[str, Any] = {}

        if not self.meta_path.exists() or not self.model_path.exists():
            return

        try:
            self.meta = json.loads(self.meta_path.read_text(encoding="utf-8"))
            model_type = self.meta.get("model_type")
            from .models.rnn_model import RNNClassifier
            from .models.lstm_model import LSTMClassifier
            from .models.bilstm_model import BiLSTMClassifier

            feature_dim = int(self.meta.get("feature_dim", 6))
            hidden_dim = int(self.meta.get("hidden_dim", 64))
            num_layers = int(self.meta.get("num_layers", 1))
            num_classes = int(self.meta.get("num_classes", len(ACTIONS)))

            if model_type == "rnn":
                self.model = RNNClassifier(feature_dim, hidden_dim, num_layers, num_classes)
            elif model_type == "lstm":
                self.model = LSTMClassifier(feature_dim, hidden_dim, num_layers, num_classes)
            else:
                self.model = BiLSTMClassifier(feature_dim, hidden_dim, num_layers, num_classes)

            state = torch.load(str(self.model_path), map_location="cpu")
            self.model.load_state_dict(state)
            self.model.eval()
            self.available = True
        except Exception:
            self.available = False
            self.model = None

    def predict_next_action(self, sequence_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not self.available or not self.model or not sequence_rows:
            return None

        category_to_id = self.meta.get("category_to_id", {})
        seq_len = int(self.meta.get("seq_len", 12))
        max_product_id = int(self.meta.get("max_product_id", 1))
        max_price = float(self.meta.get("max_price", 1.0))
        max_cart_value = float(self.meta.get("max_cart_value", 1.0))

        encoded = [
            encode_event(r, category_to_id, max_product_id, max_price, max_cart_value)
            for r in sequence_rows[-seq_len:]
        ]
        if len(encoded) < seq_len:
            pad = [np.zeros(6, dtype=np.float32) for _ in range(seq_len - len(encoded))]
            encoded = pad + encoded

        x = torch.tensor(np.array(encoded, dtype=np.float32)).unsqueeze(0)
        with torch.no_grad():
            logits = self.model(x)
            probs = torch.softmax(logits, dim=-1).squeeze(0)
            idx = int(torch.argmax(probs).item())

        return {
            "predicted_action": ACTIONS[idx],
            "confidence": round(float(probs[idx].item()), 4),
            "model_type": self.meta.get("model_type", "unknown"),
        }
