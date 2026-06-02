"""
Preprocessing pipeline v2.
Event vector (13 dims):
  action_norm, product_norm, category_id, sub_category_id,
  price_norm, rating_norm, cart_value_norm, dwell_time_norm,
  device_id, source_id, hour_of_day, intent_id, segment_id
"""
from __future__ import annotations
import csv, json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import numpy as np
import torch

ACTIONS = [
    "search", "view", "add_to_cart", "purchase", "rate_product",
    "wishlist", "remove_from_cart", "click", "compare", "share",
]
ACTION_TO_ID = {a: i for i, a in enumerate(ACTIONS)}
ACTION_ALIASES = {
    "view_detail": "view",
    "cart": "add_to_cart",
    "rate": "rate_product",
    "click_recommendation": "click",
    "click_reco": "click",
    "click_rec": "click",
}
NUM_ACTIONS = len(ACTIONS)
FEATURE_DIM = 13

DEVICES = ["desktop"]
DEVICE_TO_ID = {d: i + 1 for i, d in enumerate(DEVICES)}

SOURCES = ["organic", "email", "social", "paid_ad", "referral"]
SOURCE_TO_ID = {s: i + 1 for i, s in enumerate(SOURCES)}

INTENTS = ["browse", "compare", "buy", "abandon", "review"]
INTENT_TO_ID = {t: i + 1 for i, t in enumerate(INTENTS)}

SEGMENTS = ["casual", "buyer", "researcher", "returner", "reviewer"]
SEGMENT_TO_ID = {s: i + 1 for i, s in enumerate(SEGMENTS)}


def _safe_float(value, default=0.0):
    if value in (None, ""): return default
    try: return float(value)
    except: return default

def _safe_int(value, default=0):
    if value in (None, ""): return default
    try: return int(float(value))
    except: return default

def _parse_hour(ts):
    if not ts: return 0.0
    try: return datetime.fromisoformat(str(ts)).hour / 23.0
    except: return 0.0


def load_rows(csv_path):
    path = Path(csv_path)
    rows = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["user_id"] = _safe_int(row.get("user_id"))
            row["session_id"] = _safe_int(row.get("session_id"))
            row["step"] = _safe_int(row.get("step"))
            row["product_id"] = _safe_int(row.get("product_id"))
            row["price"] = _safe_float(row.get("price"))
            row["rating"] = _safe_float(row.get("rating"))
            row["cart_value"] = _safe_float(row.get("cart_value"))
            row["dwell_time"] = _safe_float(row.get("dwell_time"))
            row["action"] = str(row.get("action") or "search")
            row["category"] = str(row.get("category") or "unknown")
            row["sub_category"] = str(row.get("sub_category") or "unknown")
            row["device"] = str(row.get("device") or "desktop")
            row["source"] = str(row.get("source") or "organic")
            row["timestamp"] = str(row.get("timestamp") or "")
            row["intent"] = str(row.get("intent") or "browse")
            row["segment"] = str(row.get("segment") or "casual")
            rows.append(row)
    rows.sort(key=lambda r: (r["user_id"], r["timestamp"]))
    return rows


def build_category_vocab(rows):
    cats = sorted({str(r.get("category") or "unknown") for r in rows})
    return {c: i + 1 for i, c in enumerate(cats)}

def build_sub_category_vocab(rows):
    subs = sorted({str(r.get("sub_category") or "unknown") for r in rows})
    return {s: i + 1 for i, s in enumerate(subs)}


def encode_event(row, category_to_id, sub_category_to_id,
                 max_product_id, max_price, max_cart_value, max_dwell_time):
    # action normalized to [0,1] — NOT raw integer
    raw_action = str(
        row.get("action")
        or row.get("action_type")
        or row.get("interaction_type")
        or "search"
    )
    action_name = ACTION_ALIASES.get(raw_action, raw_action)
    action_norm = ACTION_TO_ID.get(action_name, 0) / max(NUM_ACTIONS - 1, 1)
    product_norm = min(_safe_float(row.get("product_id")) / max(max_product_id, 1), 1.0)
    category_id = float(category_to_id.get(str(row.get("category") or "unknown"), 0)) / max(len(category_to_id), 1)
    sub_cat_id = float(sub_category_to_id.get(str(row.get("sub_category") or "unknown"), 0)) / max(len(sub_category_to_id), 1)
    price_norm = min(_safe_float(row.get("price")) / max(max_price, 1.0), 1.0)
    rating_norm = min(_safe_float(row.get("rating")) / 5.0, 1.0)
    cart_norm = min(_safe_float(row.get("cart_value")) / max(max_cart_value, 1.0), 1.0)
    dwell_norm = min(_safe_float(row.get("dwell_time")) / max(max_dwell_time, 1.0), 1.0)
    device_id = float(DEVICE_TO_ID.get(str(row.get("device") or "desktop"), 1)) / len(DEVICES)
    source_id = float(SOURCE_TO_ID.get(str(row.get("source") or "organic"), 1)) / len(SOURCES)
    hour = _parse_hour(row.get("timestamp"))
    intent_id = float(INTENT_TO_ID.get(str(row.get("intent") or "browse"), 1)) / len(INTENTS)
    segment_id = float(SEGMENT_TO_ID.get(str(row.get("segment") or "casual"), 1)) / len(SEGMENTS)
    return np.array([
        action_norm, product_norm, category_id, sub_cat_id,
        price_norm, rating_norm, cart_norm, dwell_norm,
        device_id, source_id, hour, intent_id, segment_id,
    ], dtype=np.float32)


@dataclass
class SequenceMeta:
    category_to_id: dict
    sub_category_to_id: dict
    max_product_id: int
    max_price: float
    max_cart_value: float
    max_dwell_time: float
    seq_len: int

    def to_dict(self):
        return {
            "category_to_id": self.category_to_id,
            "sub_category_to_id": self.sub_category_to_id,
            "max_product_id": self.max_product_id,
            "max_price": self.max_price,
            "max_cart_value": self.max_cart_value,
            "max_dwell_time": self.max_dwell_time,
            "seq_len": self.seq_len,
            "feature_dim": FEATURE_DIM,
            "num_classes": NUM_ACTIONS,
            "actions": ACTIONS,
        }


class BestModelPredictor:
    def __init__(self, artifacts_dir):
        self.artifacts_dir = Path(artifacts_dir)
        self.meta_path = self.artifacts_dir / "model_best_meta.json"
        self.model_path = self.artifacts_dir / "model_best.pt"
        self.available = False
        self.model = None
        self.meta = {}
        if not self.meta_path.exists() or not self.model_path.exists():
            return
        try:
            self.meta = json.loads(self.meta_path.read_text(encoding="utf-8"))
            model_type = self.meta.get("model_type")
            from .models.rnn_model import RNNClassifier
            from .models.lstm_model import LSTMClassifier
            from .models.bilstm_model import BiLSTMClassifier
            from .models.gru_model import GRUClassifier
            from .models.bigru_model import BiGRUClassifier
            fd = int(self.meta.get("feature_dim", FEATURE_DIM))
            hd = int(self.meta.get("hidden_dim", 64))
            nl = int(self.meta.get("num_layers", 1))
            nc = int(self.meta.get("num_classes", NUM_ACTIONS))
            if model_type == "rnn":
                self.model = RNNClassifier(fd, hd, nl, nc)
            elif model_type == "lstm":
                self.model = LSTMClassifier(fd, hd, nl, nc)
            elif model_type == "bilstm":
                self.model = BiLSTMClassifier(fd, hd, nl, nc)
            elif model_type == "gru":
                self.model = GRUClassifier(fd, hd, nl, nc)
            elif model_type == "bigru":
                self.model = BiGRUClassifier(fd, hd, nl, nc)
            else:
                self.model = LSTMClassifier(fd, hd, nl, nc)
            self.model.load_state_dict(torch.load(str(self.model_path), map_location="cpu"))
            self.model.eval()
            self.available = True
        except Exception:
            self.available = False

    def predict_next_action(self, sequence_rows):
        if not self.available or not self.model or not sequence_rows:
            return None
        m = self.meta
        cat = m.get("category_to_id", {}); sub = m.get("sub_category_to_id", {})
        sl = int(m.get("seq_len", 12)); mp = int(m.get("max_product_id", 1))
        mpr = float(m.get("max_price", 1.0)); mc = float(m.get("max_cart_value", 1.0))
        md = float(m.get("max_dwell_time", 1.0))
        encoded = [encode_event(r, cat, sub, mp, mpr, mc, md) for r in sequence_rows[-sl:]]
        if len(encoded) < sl:
            encoded = [np.zeros(FEATURE_DIM, dtype=np.float32)] * (sl - len(encoded)) + encoded
        x = torch.tensor(np.array(encoded, dtype=np.float32)).unsqueeze(0)
        with torch.no_grad():
            logits = self.model(x)
            probs = torch.softmax(logits, dim=-1).squeeze(0)
            idx = int(torch.argmax(probs).item())
        return {"predicted_action": ACTIONS[idx], "confidence": round(float(probs[idx].item()), 4),
                "model_type": m.get("model_type", "unknown")}
