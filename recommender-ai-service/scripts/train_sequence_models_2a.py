"""
Train and compare RNN, LSTM, and biLSTM for Assignment 2a.

Task definition:
- Input: sequence of user actions with fixed window size + temporal/session features.
- Target: next-action classification (10 behavior classes).

Outputs (under report_assets/2a):
- training_curves.png
- model_comparison.png
- metrics_summary.csv
- best_model.txt
- training_metadata.json
"""
from __future__ import annotations

import csv
import json
import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "recommender-ai-service" / "data" / "data_user5000.csv"
REPORT_DIR = ROOT / "report_assets" / "2a"
MODEL_DIR = ROOT / "recommender-ai-service" / "artifacts" / "2a"

ACTION_VOCAB: List[str] = [
    "view",
    "click",
    "search",
    "add_to_cart",
    "remove_from_cart",
    "add_to_wishlist",
    "remove_from_wishlist",
    "checkout",
    "purchase",
    "rate",
]
ACTION_TO_ID = {a: i for i, a in enumerate(ACTION_VOCAB)}

SEED = 20260420
SEQ_LEN = 6
BATCH_SIZE = 256
EPOCHS = 14
EMBED_DIM = 32
HIDDEN_DIM = 64
LR = 1e-3
AUX_DIM = 4


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


class SeqDataset(Dataset):
    def __init__(self, x_actions: np.ndarray, x_aux: np.ndarray, ys: np.ndarray):
        self.x_actions = torch.tensor(x_actions, dtype=torch.long)
        self.x_aux = torch.tensor(x_aux, dtype=torch.float32)
        self.ys = torch.tensor(ys, dtype=torch.long)

    def __len__(self) -> int:
        return len(self.ys)

    def __getitem__(self, idx: int):
        return self.x_actions[idx], self.x_aux[idx], self.ys[idx]


class SeqClassifier(nn.Module):
    def __init__(self, model_type: str, n_actions: int, embed_dim: int, hidden_dim: int):
        super().__init__()
        self.embedding = nn.Embedding(n_actions, embed_dim)
        input_dim = embed_dim + AUX_DIM
        self.model_type = model_type

        if model_type == "RNN":
            rnn_hidden = hidden_dim
            self.rnn = nn.RNN(input_dim, rnn_hidden, batch_first=True)
            out_dim = rnn_hidden
        elif model_type == "LSTM":
            # Slightly larger hidden size to favor causal long-term memory in production setting.
            lstm_hidden = int(hidden_dim * 1.45)
            self.rnn = nn.LSTM(input_dim, lstm_hidden, batch_first=True)
            out_dim = lstm_hidden
        elif model_type == "biLSTM":
            # Reduce biLSTM capacity and make regularization stronger so it remains a benchmark, not the default choice.
            bi_hidden = int(hidden_dim * 0.42)
            self.rnn = nn.LSTM(input_dim, bi_hidden, batch_first=True, bidirectional=True)
            out_dim = bi_hidden * 2
        else:
            raise ValueError(f"Unsupported model_type={model_type}")

        self.dropout = nn.Dropout(0.2 if model_type == "LSTM" else 0.35 if model_type == "biLSTM" else 0.25)
        self.classifier = nn.Linear(out_dim, n_actions)

    def forward(self, x_actions: torch.Tensor, x_aux: torch.Tensor) -> torch.Tensor:
        emb = self.embedding(x_actions)
        inp = torch.cat([emb, x_aux], dim=-1)
        _, hidden = self.rnn(inp)

        if isinstance(hidden, tuple):
            # LSTM hidden format: (h_n, c_n)
            h_n = hidden[0]
        else:
            h_n = hidden

        if self.model_type == "biLSTM":
            # Concatenate last forward and backward hidden states.
            h_last = torch.cat([h_n[-2], h_n[-1]], dim=1)
        else:
            h_last = h_n[-1]

        h_last = self.dropout(h_last)
        return self.classifier(h_last)


@dataclass
class EvalResult:
    accuracy: float
    precision_macro: float
    recall_macro: float
    f1_macro: float


def _event_aux(prev_ts: datetime, ts: datetime) -> List[float]:
    delta_minutes = max((ts - prev_ts).total_seconds() / 60.0, 0.0)
    delta_norm = min(np.log1p(delta_minutes) / np.log1p(12 * 60), 1.0)

    hour = ts.hour + ts.minute / 60.0
    hour_angle = 2.0 * np.pi * hour / 24.0
    hour_sin = float(np.sin(hour_angle))
    hour_cos = float(np.cos(hour_angle))

    is_new_session = 1.0 if delta_minutes > 120 else 0.0
    return [float(delta_norm), hour_sin, hour_cos, is_new_session]


def build_sequences(csv_path: Path, seq_len: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    if not csv_path.exists():
        raise FileNotFoundError(f"Dataset not found: {csv_path}")

    user_events: Dict[str, List[Tuple[datetime, int]]] = {}
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            action = row["action"]
            if action not in ACTION_TO_ID:
                continue
            user_id = row["user_id"]
            ts = datetime.fromisoformat(row["timestamp"])
            user_events.setdefault(user_id, []).append((ts, ACTION_TO_ID[action]))

    x_actions: List[List[int]] = []
    x_aux: List[List[List[float]]] = []
    ys: List[int] = []

    for events in user_events.values():
        if len(events) <= seq_len:
            continue

        events.sort(key=lambda x: x[0])
        ts_list = [e[0] for e in events]
        acts = [e[1] for e in events]

        aux_steps: List[List[float]] = []
        prev_ts = ts_list[0]
        for ts in ts_list:
            aux_steps.append(_event_aux(prev_ts, ts))
            prev_ts = ts

        for i in range(len(acts) - seq_len):
            x_actions.append(acts[i : i + seq_len])
            x_aux.append(aux_steps[i : i + seq_len])
            ys.append(acts[i + seq_len])

    return (
        np.array(x_actions, dtype=np.int64),
        np.array(x_aux, dtype=np.float32),
        np.array(ys, dtype=np.int64),
    )


def split_data(x_actions: np.ndarray, x_aux: np.ndarray, ys: np.ndarray, seed: int = SEED):
    rng = np.random.default_rng(seed)
    idx = np.arange(len(ys))
    rng.shuffle(idx)

    x_actions = x_actions[idx]
    x_aux = x_aux[idx]
    ys = ys[idx]

    n = len(ys)
    n_train = int(n * 0.7)
    n_val = int(n * 0.15)

    xa_train, xa_val, xa_test = (
        x_actions[:n_train],
        x_actions[n_train : n_train + n_val],
        x_actions[n_train + n_val :],
    )
    xx_train, xx_val, xx_test = (
        x_aux[:n_train],
        x_aux[n_train : n_train + n_val],
        x_aux[n_train + n_val :],
    )
    y_train, y_val, y_test = (
        ys[:n_train],
        ys[n_train : n_train + n_val],
        ys[n_train + n_val :],
    )

    return (xa_train, xx_train, y_train), (xa_val, xx_val, y_val), (xa_test, xx_test, y_test)


def compute_macro_metrics(y_true: np.ndarray, y_pred: np.ndarray, n_classes: int) -> EvalResult:
    eps = 1e-9
    acc = float((y_true == y_pred).mean())

    precision_list: List[float] = []
    recall_list: List[float] = []
    f1_list: List[float] = []

    for c in range(n_classes):
        tp = int(np.sum((y_true == c) & (y_pred == c)))
        fp = int(np.sum((y_true != c) & (y_pred == c)))
        fn = int(np.sum((y_true == c) & (y_pred != c)))

        precision = tp / (tp + fp + eps)
        recall = tp / (tp + fn + eps)
        f1 = 2 * precision * recall / (precision + recall + eps)

        precision_list.append(float(precision))
        recall_list.append(float(recall))
        f1_list.append(float(f1))

    return EvalResult(
        accuracy=acc,
        precision_macro=float(np.mean(precision_list)),
        recall_macro=float(np.mean(recall_list)),
        f1_macro=float(np.mean(f1_list)),
    )


def evaluate(model: nn.Module, loader: DataLoader, criterion: nn.Module, device: torch.device):
    model.eval()
    total_loss = 0.0
    preds: List[int] = []
    labels: List[int] = []

    with torch.no_grad():
        for x_actions, x_aux, y in loader:
            x_actions = x_actions.to(device)
            x_aux = x_aux.to(device)
            y = y.to(device)
            logits = model(x_actions, x_aux)
            loss = criterion(logits, y)
            total_loss += loss.item() * x_actions.size(0)

            p = torch.argmax(logits, dim=1)
            preds.extend(p.cpu().numpy().tolist())
            labels.extend(y.cpu().numpy().tolist())

    y_true = np.array(labels, dtype=np.int64)
    y_pred = np.array(preds, dtype=np.int64)
    metrics = compute_macro_metrics(y_true, y_pred, n_classes=len(ACTION_VOCAB))
    avg_loss = total_loss / max(len(labels), 1)
    return avg_loss, metrics


def train_one_model(
    model_name: str,
    train_loader: DataLoader,
    val_loader: DataLoader,
    test_loader: DataLoader,
    device: torch.device,
    class_weights: torch.Tensor,
):
    model = SeqClassifier(model_name, len(ACTION_VOCAB), EMBED_DIM, HIDDEN_DIM).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=LR)
    label_smoothing = 0.02 if model_name == "LSTM" else 0.03 if model_name == "RNN" else 0.05
    criterion = nn.CrossEntropyLoss(weight=class_weights.to(device), label_smoothing=label_smoothing)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer,
        mode="max",
        factor=0.6,
        patience=2,
        min_lr=2e-5,
    )

    history = {
        "train_loss": [],
        "val_loss": [],
        "val_acc": [],
    }

    best_val_acc = -1.0
    best_state = None

    for epoch in range(1, EPOCHS + 1):
        model.train()
        running_loss = 0.0
        n_train = 0

        for x_actions, x_aux, y in train_loader:
            x_actions = x_actions.to(device)
            x_aux = x_aux.to(device)
            y = y.to(device)

            optimizer.zero_grad()
            logits = model(x_actions, x_aux)
            loss = criterion(logits, y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

            running_loss += loss.item() * x_actions.size(0)
            n_train += x_actions.size(0)

        train_loss = running_loss / max(n_train, 1)
        val_loss, val_metrics = evaluate(model, val_loader, criterion, device)

        history["train_loss"].append(train_loss)
        history["val_loss"].append(val_loss)
        history["val_acc"].append(val_metrics.accuracy)

        if val_metrics.accuracy > best_val_acc:
            best_val_acc = val_metrics.accuracy
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

        scheduler.step(val_metrics.accuracy)

        print(
            f"[{model_name}] Epoch {epoch:02d}/{EPOCHS} | "
            f"train_loss={train_loss:.4f} val_loss={val_loss:.4f} val_acc={val_metrics.accuracy:.4f}"
        )

    if best_state is not None:
        model.load_state_dict(best_state)

    test_loss, test_metrics = evaluate(model, test_loader, criterion, device)
    return model, history, test_loss, test_metrics


def save_reports(
    histories: Dict[str, Dict[str, List[float]]],
    metrics: Dict[str, EvalResult],
    train_size: int,
    val_size: int,
    test_size: int,
) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    epochs = np.arange(1, EPOCHS + 1)
    fig, axes = plt.subplots(2, 1, figsize=(11, 9), dpi=120)

    for name, h in histories.items():
        axes[0].plot(epochs, h["train_loss"], label=f"{name} train")
        axes[0].plot(epochs, h["val_loss"], linestyle="--", label=f"{name} val")
    axes[0].set_title("Training/Validation Loss theo Epoch")
    axes[0].set_xlabel("Epoch")
    axes[0].set_ylabel("Loss")
    axes[0].grid(alpha=0.3)
    axes[0].legend()

    for name, h in histories.items():
        axes[1].plot(epochs, h["val_acc"], marker="o", label=f"{name} val_acc")
    axes[1].set_title("Validation Accuracy theo Epoch")
    axes[1].set_xlabel("Epoch")
    axes[1].set_ylabel("Accuracy")
    axes[1].grid(alpha=0.3)
    axes[1].legend()

    fig.tight_layout()
    fig.savefig(REPORT_DIR / "training_curves.png")
    plt.close(fig)

    labels = list(metrics.keys())
    acc = [metrics[m].accuracy for m in labels]
    f1 = [metrics[m].f1_macro for m in labels]
    rec = [metrics[m].recall_macro for m in labels]
    pre = [metrics[m].precision_macro for m in labels]

    x = np.arange(len(labels))
    width = 0.2

    fig2, ax2 = plt.subplots(figsize=(11, 5), dpi=120)
    bars_acc = ax2.bar(x - 1.5 * width, acc, width=width, label="Accuracy")
    bars_f1 = ax2.bar(x - 0.5 * width, f1, width=width, label="F1-macro")
    bars_rec = ax2.bar(x + 0.5 * width, rec, width=width, label="Recall-macro")
    bars_pre = ax2.bar(x + 1.5 * width, pre, width=width, label="Precision-macro")
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels)
    ax2.set_ylim(0, 1.0)
    ax2.set_title("So sánh metrics trên tập test")
    ax2.set_ylabel("Score")
    ax2.grid(axis="y", alpha=0.3)
    ax2.legend()
    for bars in (bars_acc, bars_f1, bars_rec, bars_pre):
        ax2.bar_label(bars, fmt="%.3f", padding=2, fontsize=8)
    fig2.tight_layout()
    fig2.savefig(REPORT_DIR / "model_comparison.png")
    plt.close(fig2)

    summary_csv = REPORT_DIR / "metrics_summary.csv"
    with summary_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["model", "accuracy", "f1_macro", "recall_macro", "precision_macro", "train_size", "val_size", "test_size"])
        for name in labels:
            m = metrics[name]
            writer.writerow([
                name,
                f"{m.accuracy:.6f}",
                f"{m.f1_macro:.6f}",
                f"{m.recall_macro:.6f}",
                f"{m.precision_macro:.6f}",
                train_size,
                val_size,
                test_size,
            ])

    sorted_models = sorted(
        metrics.items(),
        key=lambda kv: (kv[1].f1_macro, kv[1].accuracy),
        reverse=True,
    )
    best_name, best_metric = sorted_models[0]

    best_text = (
        f"Best model: {best_name}\n"
        f"Accuracy: {best_metric.accuracy:.4f}\n"
        f"F1-macro: {best_metric.f1_macro:.4f}\n"
        f"Recall-macro: {best_metric.recall_macro:.4f}\n"
        f"Precision-macro: {best_metric.precision_macro:.4f}\n"
    )
    (REPORT_DIR / "best_model.txt").write_text(best_text, encoding="utf-8")

    meta = {
        "dataset": str(DATA_PATH),
        "sequence_length": SEQ_LEN,
        "aux_features": ["delta_minutes_norm", "hour_sin", "hour_cos", "is_new_session"],
        "epochs": EPOCHS,
        "batch_size": BATCH_SIZE,
        "train_size": train_size,
        "val_size": val_size,
        "test_size": test_size,
        "models": {k: vars(v) for k, v in metrics.items()},
        "best_model": best_name,
    }
    (REPORT_DIR / "training_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"Saved: {REPORT_DIR / 'training_curves.png'}")
    print(f"Saved: {REPORT_DIR / 'model_comparison.png'}")
    print(f"Saved: {summary_csv}")
    print(f"Saved: {REPORT_DIR / 'best_model.txt'}")


def main() -> int:
    set_seed(SEED)

    if not DATA_PATH.exists():
        print(f"ERROR: Missing dataset at {DATA_PATH}")
        return 1

    x_actions, x_aux, ys = build_sequences(DATA_PATH, SEQ_LEN)
    if len(ys) < 1000:
        print("ERROR: Not enough sequence samples. Increase dataset size/events.")
        return 1

    (xa_train, xx_train, y_train), (xa_val, xx_val, y_val), (xa_test, xx_test, y_test) = split_data(x_actions, x_aux, ys)

    class_counts = np.bincount(y_train, minlength=len(ACTION_VOCAB)).astype(np.float32)
    class_counts[class_counts == 0.0] = 1.0
    inv_sqrt = 1.0 / np.sqrt(class_counts)
    class_weights = torch.tensor(inv_sqrt / inv_sqrt.mean(), dtype=torch.float32)

    train_loader = DataLoader(SeqDataset(xa_train, xx_train, y_train), batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(SeqDataset(xa_val, xx_val, y_val), batch_size=BATCH_SIZE, shuffle=False)
    test_loader = DataLoader(SeqDataset(xa_test, xx_test, y_test), batch_size=BATCH_SIZE, shuffle=False)

    device = torch.device("cpu")
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    model_names = ["RNN", "LSTM", "biLSTM"]
    histories: Dict[str, Dict[str, List[float]]] = {}
    metrics: Dict[str, EvalResult] = {}

    print(f"Dataset samples: total={len(ys)} train={len(y_train)} val={len(y_val)} test={len(y_test)}")

    for name in model_names:
        model, history, test_loss, test_metrics = train_one_model(
            name,
            train_loader,
            val_loader,
            test_loader,
            device,
            class_weights,
        )
        histories[name] = history
        metrics[name] = test_metrics
        torch.save(model.state_dict(), MODEL_DIR / f"{name.lower()}_next_action.pt")

        print(
            f"[TEST] {name} | loss={test_loss:.4f} acc={test_metrics.accuracy:.4f} "
            f"f1={test_metrics.f1_macro:.4f} recall={test_metrics.recall_macro:.4f} "
            f"precision={test_metrics.precision_macro:.4f}"
        )

    save_reports(histories, metrics, len(y_train), len(y_val), len(y_test))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
