"""
LSTM Behavior Model — PyTorch (primary model, bám sát yêu cầu môn)
────────────────────────────────────────────────────────────────────
Architecture:
  input: sequence of events (view/search/cart/purchase/rate)
  each event: [product_id_norm, interaction_type, timestamp_norm, price_range, category_idx_norm]
  LSTM → FC heads → [engagement_score, purchase_propensity, segment_logits]

Fallback: nếu checkpoint không tồn tại → rule-based profile.
"""
from __future__ import annotations
import logging
import numpy as np
from pathlib import Path
from typing import Any

import torch
import torch.nn as nn

logger = logging.getLogger(__name__)

MAX_SEQ_LEN = 20
FEATURE_DIM = 5   # [product_id_norm, interaction_type_norm, timestamp_norm, price_range_norm, category_norm]
MAX_PRODUCT_ID = 500
MAX_CATEGORY_IDX = 30
SEGMENTS = ["new", "casual", "engaged", "loyal", "champion"]

LSTM_MODEL_PATH = Path("artifacts/lstm_behavior_model.pt")


class LSTMBehaviorModel(nn.Module):
    """
    LSTM sequence model cho dự đoán hành vi người dùng.
    Bám sát yêu cầu môn: LSTM + sequence input + multi-head output.
    """
    def __init__(
        self,
        input_dim: int = FEATURE_DIM,
        hidden_dim: int = 64,
        num_layers: int = 2,
        n_segments: int = 5,
        dropout: float = 0.2,
    ):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers

        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.dropout = nn.Dropout(dropout)

        # Multi-head outputs
        self.engagement_head  = nn.Sequential(nn.Linear(hidden_dim, 16), nn.ReLU(), nn.Linear(16, 1), nn.Sigmoid())
        self.propensity_head  = nn.Sequential(nn.Linear(hidden_dim, 16), nn.ReLU(), nn.Linear(16, 1), nn.Sigmoid())
        self.segment_head     = nn.Linear(hidden_dim, n_segments)

    def forward(self, x: torch.Tensor):
        """
        x: (batch, seq_len, feature_dim)
        Returns: (engagement, propensity, segment_logits)
        """
        out, _ = self.lstm(x)
        # Use last timestep output
        last = out[:, -1, :]
        last = self.dropout(last)
        return (
            self.engagement_head(last).squeeze(-1),
            self.propensity_head(last).squeeze(-1),
            self.segment_head(last),
        )


# ── Singleton loader ──────────────────────────────────────────────────────────

_model: LSTMBehaviorModel | None = None
_model_loaded = False


def load_model() -> LSTMBehaviorModel | None:
    global _model, _model_loaded
    if _model_loaded:
        return _model
    _model_loaded = True

    if not LSTM_MODEL_PATH.exists():
        logger.info("LSTM checkpoint not found at %s — will use rule-based fallback", LSTM_MODEL_PATH)
        return None
    try:
        m = LSTMBehaviorModel()
        state = torch.load(str(LSTM_MODEL_PATH), map_location="cpu")
        m.load_state_dict(state)
        m.eval()
        _model = m
        logger.info("LSTM behavior model loaded from %s", LSTM_MODEL_PATH)
        return _model
    except Exception as exc:
        logger.warning("Could not load LSTM model: %s — using rule-based fallback", exc)
        return None


def encode_sequence(events: list[dict]) -> torch.Tensor:
    """
    Encode list of event dicts → tensor (1, MAX_SEQ_LEN, FEATURE_DIM).
    Event keys: product_id, interaction_type (str or int), timestamp, price_range, category_idx
    """
    TYPE_MAP = {"view": 0, "search": 1, "cart": 2, "purchase": 3, "rate": 4}
    mat = np.zeros((MAX_SEQ_LEN, FEATURE_DIM), dtype=np.float32)

    for i, e in enumerate(events[:MAX_SEQ_LEN]):
        pid = int(e.get("product_id") or e.get("book_id") or 0)
        mat[i, 0] = min(pid / MAX_PRODUCT_ID, 1.0)

        itype = e.get("interaction_type", 0)
        if isinstance(itype, str):
            itype = TYPE_MAP.get(itype, 0)
        mat[i, 1] = int(itype) / 4.0

        ts = int(e.get("timestamp", 0))
        mat[i, 2] = min((ts % (30 * 86400)) / (30 * 86400), 1.0)

        mat[i, 3] = int(e.get("price_range", 2)) / 4.0

        cat_idx = int(e.get("category_idx", 0))
        mat[i, 4] = min(cat_idx / MAX_CATEGORY_IDX, 1.0)

    return torch.tensor(mat).unsqueeze(0)  # (1, MAX_SEQ_LEN, FEATURE_DIM)


def predict(events: list[dict]) -> dict[str, Any] | None:
    """
    Run LSTM inference on event sequence.
    Returns dict or None (caller should fallback to rule-based).
    """
    if not events:
        return None

    model = load_model()
    if model is None:
        return None

    try:
        x = encode_sequence(events)
        with torch.no_grad():
            eng, prop, seg_logits = model(x)

        seg_idx = int(seg_logits.argmax(dim=-1).item())
        segment = SEGMENTS[seg_idx] if seg_idx < len(SEGMENTS) else "casual"

        return {
            "engagement_score":    round(float(eng.item()), 3),
            "purchase_propensity": round(float(prop.item()), 3),
            "customer_segment":    segment,
            "model_source":        "lstm_pytorch",
        }
    except Exception as exc:
        logger.warning("LSTM inference failed: %s", exc)
        return None
