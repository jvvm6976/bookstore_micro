"""
Dataset builder v2.
- Sequence window stays WITHIN session boundary (no cross-session noise)
- Prints y distribution + 5 decoded samples for debugging
- Stratified split 70/15/15
"""
from __future__ import annotations
from collections import defaultdict, Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import numpy as np
import torch
from torch.utils.data import Dataset
from .preprocess import ACTION_TO_ID, ACTIONS, SequenceMeta, build_category_vocab, build_sub_category_vocab, encode_event, load_rows

@dataclass
class SplitData:
    X_train: np.ndarray
    y_train: np.ndarray
    X_val: np.ndarray
    y_val: np.ndarray
    X_test: np.ndarray
    y_test: np.ndarray
    meta: SequenceMeta


class BehaviorSequenceDataset(Dataset):
    def __init__(self, X, y):
        self.X = torch.tensor(X, dtype=torch.float32)
        self.y = torch.tensor(y, dtype=torch.long)
    def __len__(self): return int(self.X.shape[0])
    def __getitem__(self, idx): return self.X[idx], self.y[idx]


def _stratified_split_indices(y, seed=42):
    rng = np.random.default_rng(seed)
    train_idx, val_idx, test_idx = [], [], []
    for label in np.unique(y):
        idx = np.where(y == label)[0]; rng.shuffle(idx); n = len(idx)
        n_train = max(1, int(n * 0.70)); n_val = max(1, int(n * 0.15))
        n_test = n - n_train - n_val
        if n_test <= 0:
            n_test = 1
            if n_train > n_val: n_train -= 1
            else: n_val -= 1
        train_idx.extend(idx[:n_train].tolist())
        val_idx.extend(idx[n_train:n_train + n_val].tolist())
        test_idx.extend(idx[n_train + n_val:].tolist())
    rng.shuffle(train_idx); rng.shuffle(val_idx); rng.shuffle(test_idx)
    return np.array(train_idx), np.array(val_idx), np.array(test_idx)


def print_distribution(name, y, num_classes=10):
    counts = np.bincount(y.astype(np.int64), minlength=num_classes)
    total = len(y)
    print(f"\n  {name} distribution (n={total:,}):")
    for i, c in enumerate(counts):
        bar = "#" * int(c / max(total, 1) * 40)
        print(f"    {ACTIONS[i]:<20} {c:>6,} ({c/max(total,1)*100:5.1f}%) {bar}")


def print_sample_sequences(X, y, n=5):
    print(f"\n  Sample sequences (showing action_norm -> decoded action):")
    for i in range(min(n, len(X))):
        seq = X[i]  # shape (seq_len, feature_dim)
        # action_norm is dim 0, decode back: action_id = round(norm * 9)
        x_actions = [ACTIONS[min(round(float(seq[t, 0]) * 9), 9)] for t in range(seq.shape[0])]
        y_action = ACTIONS[int(y[i])]
        print(f"    [{', '.join(x_actions[-4:])} ...] -> y={y_action}")


def build_sequence_samples(csv_path, seq_len=12):
    rows = load_rows(csv_path)
    if not rows: raise ValueError("No rows found")

    # Group by SESSION (not user) to avoid cross-session noise
    by_session: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        sid = int(row.get("session_id") or row.get("user_id") or 0)
        by_session[sid].append(row)

    category_to_id = build_category_vocab(rows)
    sub_category_to_id = build_sub_category_vocab(rows)
    max_product_id = max(int(r["product_id"]) for r in rows)
    max_price = max(float(r["price"]) for r in rows)
    max_cart_value = max(float(r["cart_value"]) for r in rows) or 1.0
    max_dwell_time = max(float(r["dwell_time"]) for r in rows) or 1.0

    X_list, y_list = [], []

    for session_rows in by_session.values():
        # Sessions already sorted by timestamp via load_rows
        if len(session_rows) <= seq_len:
            continue
        encoded = [
            encode_event(r, category_to_id, sub_category_to_id,
                         max_product_id, max_price, max_cart_value, max_dwell_time)
            for r in session_rows
        ]
        action_ids = [ACTION_TO_ID.get(str(r.get("action")), 0) for r in session_rows]
        for i in range(seq_len, len(encoded)):
            X_list.append(np.array(encoded[i - seq_len:i], dtype=np.float32))
            y_list.append(int(action_ids[i]))

    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.int64)
    meta = SequenceMeta(
        category_to_id=category_to_id, sub_category_to_id=sub_category_to_id,
        max_product_id=max_product_id, max_price=max_price,
        max_cart_value=max_cart_value, max_dwell_time=max_dwell_time, seq_len=seq_len,
    )
    return X, y, meta


def load_split_data(csv_path, seq_len=12, seed=42, verbose=False):
    X, y, meta = build_sequence_samples(csv_path, seq_len=seq_len)
    if len(X) < 50: raise ValueError("Not enough samples")
    train_idx, val_idx, test_idx = _stratified_split_indices(y, seed=seed)
    split = SplitData(
        X_train=X[train_idx], y_train=y[train_idx],
        X_val=X[val_idx], y_val=y[val_idx],
        X_test=X[test_idx], y_test=y[test_idx],
        meta=meta,
    )
    if verbose:
        print(f"\n  Total samples: {len(X):,}  |  seq_len={seq_len}  |  feature_dim={X.shape[2]}")
        print_distribution("y_train", split.y_train)
        print_distribution("y_val",   split.y_val)
        print_distribution("y_test",  split.y_test)
        print_sample_sequences(split.X_train, split.y_train)
    return split