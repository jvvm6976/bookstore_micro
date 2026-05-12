from __future__ import annotations

import csv
import json
import random
from pathlib import Path
from typing import Any

try:
    import matplotlib
    matplotlib.use('Agg')  # Headless backend for Docker
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("⚠ matplotlib not available, plots will be skipped")

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from .dataset import BehaviorSequenceDataset, SplitData
from .preprocess import ACTIONS


def set_seed(seed: int = 42) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def confusion_matrix(y_true: np.ndarray, y_pred: np.ndarray, num_classes: int) -> np.ndarray:
    cm = np.zeros((num_classes, num_classes), dtype=np.int64)
    for t, p in zip(y_true, y_pred):
        cm[int(t), int(p)] += 1
    return cm


def compute_classification_metrics(y_true: np.ndarray, y_pred: np.ndarray, num_classes: int) -> dict[str, Any]:
    cm = confusion_matrix(y_true, y_pred, num_classes)
    accuracy = float((y_true == y_pred).mean()) if len(y_true) else 0.0

    precisions = []
    recalls = []
    f1s = []
    for i in range(num_classes):
        tp = float(cm[i, i])
        fp = float(cm[:, i].sum() - tp)
        fn = float(cm[i, :].sum() - tp)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        precisions.append(precision)
        recalls.append(recall)
        f1s.append(f1)

    return {
        "accuracy": round(accuracy, 6),
        "precision": round(float(np.mean(precisions)), 6),
        "recall": round(float(np.mean(recalls)), 6),
        "f1_score": round(float(np.mean(f1s)), 6),
        "confusion_matrix": cm.tolist(),
    }


def train_classifier(
    model: torch.nn.Module,
    split_data: SplitData,
    model_name: str,
    model_type: str,
    artifacts_dir: Path,
    epochs: int = 15,
    batch_size: int = 64,
    learning_rate: float = 1e-3,
) -> dict[str, Any]:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)

    train_ds = BehaviorSequenceDataset(split_data.X_train, split_data.y_train)
    val_ds = BehaviorSequenceDataset(split_data.X_val, split_data.y_val)
    test_ds = BehaviorSequenceDataset(split_data.X_test, split_data.y_test)

    # Handle class imbalance for better macro-metrics (precision/recall/F1).
    # Use a mild weighting scheme (inverse-sqrt frequency) to avoid overcorrection.
    train_labels = split_data.y_train.astype(np.int64)
    class_counts = np.bincount(train_labels, minlength=len(ACTIONS)).astype(np.float64)
    safe_counts = np.where(class_counts > 0, class_counts, 1.0)
    class_weights_np = 1.0 / np.sqrt(safe_counts)
    class_weights_np = class_weights_np / np.mean(class_weights_np)
    class_weights_np = np.clip(class_weights_np, 0.5, 2.0)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False)

    class_weights_t = torch.tensor(class_weights_np, dtype=torch.float32, device=device)
    criterion = nn.CrossEntropyLoss(weight=class_weights_t)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)

    history = {
        "train_loss": [],
        "val_loss": [],
        "val_accuracy": [],
    }

    for _ in range(epochs):
        model.train()
        total_train_loss = 0.0
        train_batches = 0

        for xb, yb in train_loader:
            xb = xb.to(device)
            yb = yb.to(device)
            optimizer.zero_grad()
            logits = model(xb)
            loss = criterion(logits, yb)
            loss.backward()
            optimizer.step()

            total_train_loss += float(loss.item())
            train_batches += 1

        model.eval()
        total_val_loss = 0.0
        val_batches = 0
        val_true: list[int] = []
        val_pred: list[int] = []

        with torch.no_grad():
            for xb, yb in val_loader:
                xb = xb.to(device)
                yb = yb.to(device)
                logits = model(xb)
                loss = criterion(logits, yb)
                total_val_loss += float(loss.item())
                val_batches += 1

                preds = torch.argmax(logits, dim=-1)
                val_true.extend(yb.cpu().numpy().tolist())
                val_pred.extend(preds.cpu().numpy().tolist())

        val_acc = float((np.array(val_true) == np.array(val_pred)).mean()) if val_true else 0.0
        history["train_loss"].append(total_train_loss / max(train_batches, 1))
        history["val_loss"].append(total_val_loss / max(val_batches, 1))
        history["val_accuracy"].append(val_acc)

    test_true: list[int] = []
    test_pred: list[int] = []
    model.eval()
    with torch.no_grad():
        for xb, yb in test_loader:
            xb = xb.to(device)
            logits = model(xb)
            preds = torch.argmax(logits, dim=-1)
            test_true.extend(yb.numpy().tolist())
            test_pred.extend(preds.cpu().numpy().tolist())

    metrics = compute_classification_metrics(
        np.array(test_true, dtype=np.int64),
        np.array(test_pred, dtype=np.int64),
        num_classes=len(ACTIONS),
    )

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    model_path = artifacts_dir / f"{model_name}_model.pt"
    torch.save(model.state_dict(), str(model_path))

    meta = split_data.meta.to_dict()
    meta.update(
        {
            "model_name": model_name,
            "model_type": model_type,
            "hidden_dim": 64,
            "num_layers": 1,
            "num_classes": len(ACTIONS),
            "class_balance": {
                "class_counts": class_counts.astype(int).tolist(),
                "class_weights": [round(float(x), 6) for x in class_weights_np.tolist()],
                "sampler": "none",
                "loss": "cross_entropy_weighted",
            },
            "metrics": metrics,
        }
    )
    with (artifacts_dir / f"{model_name}_model_meta.json").open("w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return {
        "model_name": model_name,
        "model_type": model_type,
        "model_path": str(model_path),
        "history": history,
        "metrics": metrics,
        "meta": meta,
    }


def save_metrics_files(results: list[dict[str, Any]], artifacts_dir: Path) -> None:
    rows = []
    for r in results:
        rows.append(
            {
                "model": r["model_name"],
                "accuracy": r["metrics"]["accuracy"],
                "precision": r["metrics"]["precision"],
                "recall": r["metrics"]["recall"],
                "f1_score": r["metrics"]["f1_score"],
            }
        )

    with (artifacts_dir / "metrics_report.json").open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    with (artifacts_dir / "metrics_report.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["model", "accuracy", "precision", "recall", "f1_score"],
        )
        writer.writeheader()
        writer.writerows(rows)


def plot_training_histories(results: list[dict[str, Any]], plots_dir: Path) -> None:
    if not HAS_MATPLOTLIB:
        print("⚠ Skipping plots (matplotlib not available)")
        return
    
    plots_dir.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(10, 6))
    for r in results:
        plt.plot(r["history"]["train_loss"], label=f"{r['model_name'].upper()} train")
    plt.title("Training Loss")
    plt.xlabel("Epoch")
    plt.ylabel("Loss")
    plt.legend()
    plt.tight_layout()
    plt.savefig(plots_dir / "training_loss.png")
    plt.close()

    plt.figure(figsize=(10, 6))
    for r in results:
        plt.plot(r["history"]["val_loss"], label=f"{r['model_name'].upper()} val")
    plt.title("Validation Loss")
    plt.xlabel("Epoch")
    plt.ylabel("Loss")
    plt.legend()
    plt.tight_layout()
    plt.savefig(plots_dir / "validation_loss.png")
    plt.close()

    labels = [r["model_name"].upper() for r in results]
    accuracies = [r["metrics"]["accuracy"] for r in results]

    plt.figure(figsize=(8, 5))
    plt.bar(labels, accuracies, color=["#2E86AB", "#F18F01", "#2A9D8F"])
    plt.title("Accuracy Comparison")
    plt.ylabel("Accuracy")
    plt.ylim(0, 1)
    plt.tight_layout()
    plt.savefig(plots_dir / "accuracy_comparison.png")
    plt.close()

    f1_scores = [r["metrics"]["f1_score"] for r in results]
    x = np.arange(len(labels))
    width = 0.35

    plt.figure(figsize=(8, 5))
    plt.bar(x - width / 2, accuracies, width=width, label="Accuracy", color="#4C78A8")
    plt.bar(x + width / 2, f1_scores, width=width, label="F1", color="#F58518")
    plt.title("Model Comparison")
    plt.xticks(x, labels)
    plt.ylim(0, 1)
    plt.legend()
    plt.tight_layout()
    plt.savefig(plots_dir / "model_comparison_bar.png")
    plt.close()
