from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch.utils.data import Dataset

from .preprocess import ACTION_TO_ID, SequenceMeta, build_category_vocab, encode_event, load_rows


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
    def __init__(self, X: np.ndarray, y: np.ndarray):
        self.X = torch.tensor(X, dtype=torch.float32)
        self.y = torch.tensor(y, dtype=torch.long)

    def __len__(self) -> int:
        return int(self.X.shape[0])

    def __getitem__(self, idx: int):
        return self.X[idx], self.y[idx]


def _stratified_split_indices(y: np.ndarray, seed: int = 42) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    train_idx: list[int] = []
    val_idx: list[int] = []
    test_idx: list[int] = []

    for label in np.unique(y):
        idx = np.where(y == label)[0]
        rng.shuffle(idx)
        n = len(idx)
        n_train = max(1, int(n * 0.7))
        n_val = max(1, int(n * 0.15))
        n_test = n - n_train - n_val
        if n_test <= 0:
            n_test = 1
            if n_train > n_val:
                n_train -= 1
            else:
                n_val -= 1

        train_idx.extend(idx[:n_train].tolist())
        val_idx.extend(idx[n_train:n_train + n_val].tolist())
        test_idx.extend(idx[n_train + n_val:].tolist())

    rng.shuffle(train_idx)
    rng.shuffle(val_idx)
    rng.shuffle(test_idx)

    return np.array(train_idx), np.array(val_idx), np.array(test_idx)


def build_sequence_samples(csv_path: str | Path, seq_len: int = 12) -> tuple[np.ndarray, np.ndarray, SequenceMeta]:
    rows = load_rows(csv_path)
    if not rows:
        raise ValueError("No rows found in dataset")

    by_user: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_user[int(row["user_id"])].append(row)

    category_to_id = build_category_vocab(rows)
    max_product_id = max(int(r["product_id"]) for r in rows)
    max_price = max(float(r["price"]) for r in rows)
    max_cart_value = max(float(r["cart_value"]) for r in rows)

    X_list: list[np.ndarray] = []
    y_list: list[int] = []

    for user_rows in by_user.values():
        if len(user_rows) <= seq_len:
            continue

        encoded_events = [
            encode_event(r, category_to_id, max_product_id, max_price, max_cart_value)
            for r in user_rows
        ]
        action_ids = [ACTION_TO_ID.get(str(r.get("action")), 0) for r in user_rows]

        for i in range(seq_len, len(encoded_events)):
            X_list.append(np.array(encoded_events[i - seq_len:i], dtype=np.float32))
            y_list.append(int(action_ids[i]))

    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.int64)

    meta = SequenceMeta(
        category_to_id=category_to_id,
        max_product_id=max_product_id,
        max_price=max_price,
        max_cart_value=max_cart_value,
        seq_len=seq_len,
    )
    return X, y, meta


def load_split_data(csv_path: str | Path, seq_len: int = 12, seed: int = 42) -> SplitData:
    X, y, meta = build_sequence_samples(csv_path, seq_len=seq_len)
    if len(X) < 50:
        raise ValueError("Not enough sequence samples for train/val/test split")

    train_idx, val_idx, test_idx = _stratified_split_indices(y, seed=seed)

    return SplitData(
        X_train=X[train_idx],
        y_train=y[train_idx],
        X_val=X[val_idx],
        y_val=y[val_idx],
        X_test=X[test_idx],
        y_test=y[test_idx],
        meta=meta,
    )
