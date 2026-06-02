"""
Common training utilities v2.
- hidden_dim=128 (was 64)
- Adam + weight_decay=1e-4
- CrossEntropyLoss weighted: 1/sqrt(count), normalised, clipped [0.5,2.0]
- Dropout=0.3
- Early Stopping patience=5 on val_loss
- Prints y_pred distribution + confusion matrix per run
- ROC-AUC macro, PR-AUC macro, Generalization Gap
"""
from __future__ import annotations
import csv, json, random
from pathlib import Path
from typing import Any
try:
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from .dataset import BehaviorSequenceDataset, SplitData, print_distribution
from .preprocess import ACTIONS
NUM_CLASSES = len(ACTIONS)
HIDDEN_DIM = 256


def set_seed(seed=42):
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    if torch.cuda.is_available(): torch.cuda.manual_seed_all(seed)


def _confusion_matrix(y_true, y_pred, num_classes):
    cm = np.zeros((num_classes, num_classes), dtype=np.int64)
    for t, p in zip(y_true, y_pred): cm[int(t), int(p)] += 1
    return cm


def _roc_auc_macro(y_true, y_prob, num_classes):
    aucs = []
    for c in range(num_classes):
        binary = (y_true == c).astype(int)
        if binary.sum() == 0 or binary.sum() == len(binary): continue
        scores = y_prob[:, c]; order = np.argsort(-scores); bs = binary[order]
        tp = np.cumsum(bs); fp = np.cumsum(1 - bs)
        tpr = np.concatenate([[0.0], tp / max(binary.sum(), 1)])
        fpr = np.concatenate([[0.0], fp / max((1 - binary).sum(), 1)])
        aucs.append(abs(float(np.trapz(tpr, fpr))))
    return round(float(np.mean(aucs)) if aucs else 0.0, 6)


def _pr_auc_macro(y_true, y_prob, num_classes):
    aucs = []
    for c in range(num_classes):
        binary = (y_true == c).astype(int)
        if binary.sum() == 0: continue
        scores = y_prob[:, c]; order = np.argsort(-scores); bs = binary[order]
        tp = np.cumsum(bs); fp = np.cumsum(1 - bs)
        prec = np.concatenate([[1.0], tp / np.maximum(tp + fp, 1)])
        rec = np.concatenate([[0.0], tp / max(binary.sum(), 1)])
        aucs.append(abs(float(np.trapz(prec, rec))))
    return round(float(np.mean(aucs)) if aucs else 0.0, 6)


def compute_classification_metrics(y_true, y_pred, y_prob, num_classes):
    cm = _confusion_matrix(y_true, y_pred, num_classes)
    accuracy = float((y_true == y_pred).mean()) if len(y_true) else 0.0
    precisions, recalls, f1s = [], [], []
    for i in range(num_classes):
        tp = float(cm[i, i]); fp = float(cm[:, i].sum() - tp); fn = float(cm[i, :].sum() - tp)
        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f = (2 * p * r) / (p + r) if (p + r) > 0 else 0.0
        precisions.append(p); recalls.append(r); f1s.append(f)
    return {
        "accuracy": round(accuracy, 6), "precision": round(float(np.mean(precisions)), 6),
        "recall": round(float(np.mean(recalls)), 6), "f1_score": round(float(np.mean(f1s)), 6),
        "roc_auc": _roc_auc_macro(y_true, y_prob, num_classes),
        "pr_auc": _pr_auc_macro(y_true, y_prob, num_classes),
        "confusion_matrix": cm.tolist(),
    }


def compute_class_weights(y_train, num_classes):
    counts = np.bincount(y_train.astype(np.int64), minlength=num_classes).astype(np.float64)
    safe = np.where(counts > 0, counts, 1.0); raw = 1.0 / np.sqrt(safe)
    return np.clip(raw / np.mean(raw), 0.5, 2.0)


def train_classifier(model, split_data, model_name, model_type, artifacts_dir,
                     epochs=30, batch_size=128, learning_rate=1e-3,
                     weight_decay=1e-4, early_stopping_patience=5,
                     run_id="0", verbose=True):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)
    train_loader = DataLoader(BehaviorSequenceDataset(split_data.X_train, split_data.y_train), batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(BehaviorSequenceDataset(split_data.X_val, split_data.y_val), batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(BehaviorSequenceDataset(split_data.X_test, split_data.y_test), batch_size=batch_size, shuffle=False)
    cw_np = compute_class_weights(split_data.y_train, NUM_CLASSES)
    criterion = nn.CrossEntropyLoss(weight=torch.tensor(cw_np, dtype=torch.float32, device=device))
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate, weight_decay=weight_decay)
    history = {"train_loss": [], "val_loss": [], "val_accuracy": []}
    best_val_loss = float("inf"); best_train_loss = float("inf"); patience_counter = 0
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    # Unique tmp checkpoint per model+run — no cross-run reuse
    tmp_ckpt_dir = artifacts_dir / "_tmp_checkpoints"
    tmp_ckpt_dir.mkdir(parents=True, exist_ok=True)
    best_ckpt = tmp_ckpt_dir / f"{model_name}_run{run_id}_best.pt"
    if best_ckpt.exists():
        best_ckpt.unlink()  # remove stale checkpoint

    for epoch in range(epochs):
        model.train(); total_train, n_train = 0.0, 0
        for xb, yb in train_loader:
            xb, yb = xb.to(device), yb.to(device); optimizer.zero_grad()
            loss = criterion(model(xb), yb); loss.backward(); optimizer.step()
            total_train += float(loss.item()); n_train += 1
        avg_train = total_train / max(n_train, 1)
        model.eval(); total_val, n_val = 0.0, 0; val_true = []; val_pred = []
        with torch.no_grad():
            for xb, yb in val_loader:
                xb, yb = xb.to(device), yb.to(device); logits = model(xb)
                total_val += float(criterion(logits, yb).item()); n_val += 1
                val_pred.extend(torch.argmax(logits, dim=-1).cpu().numpy().tolist())
                val_true.extend(yb.cpu().numpy().tolist())
        avg_val = total_val / max(n_val, 1)
        val_acc = float((np.array(val_true) == np.array(val_pred)).mean()) if val_true else 0.0
        history["train_loss"].append(avg_train); history["val_loss"].append(avg_val); history["val_accuracy"].append(val_acc)
        if avg_val < best_val_loss:
            best_val_loss = avg_val; best_train_loss = avg_train; patience_counter = 0
            torch.save(model.state_dict(), str(best_ckpt))
        else:
            patience_counter += 1
            if patience_counter >= early_stopping_patience:
                if verbose: print(f"  Early stop at epoch {epoch + 1}")
                break

    if best_ckpt.exists():
        model.load_state_dict(torch.load(str(best_ckpt), map_location=device)); best_ckpt.unlink()
    model.eval(); test_true = []; test_pred = []; test_probs = []
    with torch.no_grad():
        for xb, yb in test_loader:
            xb = xb.to(device); logits = model(xb)
            test_probs.append(torch.softmax(logits, dim=-1).cpu().numpy())
            test_pred.extend(torch.argmax(logits, dim=-1).cpu().numpy().tolist())
            test_true.extend(yb.numpy().tolist())

    y_true = np.array(test_true, dtype=np.int64)
    y_pred_arr = np.array(test_pred, dtype=np.int64)
    y_prob = np.vstack(test_probs)
    metrics = compute_classification_metrics(y_true, y_pred_arr, y_prob, NUM_CLASSES)
    metrics["train_loss"] = round(best_train_loss, 6)
    metrics["val_loss"] = round(best_val_loss, 6)
    metrics["generalization_gap"] = round(best_val_loss - best_train_loss, 6)

    if verbose:
        print_distribution("  y_pred (test)", y_pred_arr)
        cm = np.array(metrics["confusion_matrix"])
        print("\n  Confusion matrix (rows=true, cols=pred):")
        header = "         " + "".join(f"{a[:5]:>7}" for a in ACTIONS)
        print(header)
        for i, row_vals in enumerate(cm):
            print(f"  {ACTIONS[i][:8]:<8} " + "".join(f"{v:>7}" for v in row_vals))

    model_path = artifacts_dir / f"{model_name}_model.pt"
    torch.save(model.state_dict(), str(model_path))
    meta = split_data.meta.to_dict()
    meta.update({"model_name": model_name, "model_type": model_type,
                 "hidden_dim": HIDDEN_DIM, "num_layers": 1, "num_classes": NUM_CLASSES,
                 "class_weights": [round(float(w), 6) for w in cw_np.tolist()], "metrics": metrics})
    (artifacts_dir / f"{model_name}_model_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"model_name": model_name, "model_type": model_type, "model_path": str(model_path),
            "history": history, "metrics": metrics, "meta": meta, "class_weights_np": cw_np}


def save_class_weights_csv(class_weights, artifacts_dir):
    with (artifacts_dir / "class_weights.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["class_id", "action", "weight"]); writer.writeheader()
        for i, (action, w) in enumerate(zip(ACTIONS, class_weights)):
            writer.writerow({"class_id": i, "action": action, "weight": round(float(w), 6)})

def save_hyperparameters_json(artifacts_dir, **kwargs):
    (artifacts_dir / "hyperparameters.json").write_text(json.dumps(kwargs, indent=2, ensure_ascii=False), encoding="utf-8")

def save_all_runs_csv(all_runs, artifacts_dir):
    fieldnames = ["model","run","accuracy","precision","recall","f1_score","roc_auc","pr_auc","train_loss","val_loss","generalization_gap"]
    with (artifacts_dir / "all_runs_metrics.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames); writer.writeheader()
        for entry in all_runs:
            m = entry.get("metrics", {})
            writer.writerow({"model": entry["model_name"], "run": entry["run"],
                "accuracy": m.get("accuracy",0), "precision": m.get("precision",0),
                "recall": m.get("recall",0), "f1_score": m.get("f1_score",0),
                "roc_auc": m.get("roc_auc",0), "pr_auc": m.get("pr_auc",0),
                "train_loss": m.get("train_loss",0), "val_loss": m.get("val_loss",0),
                "generalization_gap": m.get("generalization_gap",0)})

def save_model_summary_csv(summary_rows, artifacts_dir):
    fieldnames = ["model","avg_accuracy","avg_precision","avg_recall","avg_macro_f1","avg_roc_auc","avg_pr_auc","avg_train_loss","avg_val_loss","avg_generalization_gap","num_runs"]
    with (artifacts_dir / "model_summary.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames); writer.writeheader(); writer.writerows(summary_rows)


def save_metrics_files(results, artifacts_dir):
    artifacts_dir = Path(artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    metrics_report = []
    for r in results:
        m = r.get("metrics", {})
        row = {
            "model": r.get("model_name", "unknown"),
            "accuracy": m.get("accuracy", 0.0),
            "precision": m.get("precision", 0.0),
            "recall": m.get("recall", 0.0),
            "f1_score": m.get("f1_score", 0.0),
            "roc_auc": m.get("roc_auc", 0.0),
            "pr_auc": m.get("pr_auc", 0.0),
            "train_loss": m.get("train_loss", 0.0),
            "val_loss": m.get("val_loss", 0.0),
            "generalization_gap": m.get("generalization_gap", 0.0),
        }
        rows.append(row)
        metrics_report.append(row)

    (artifacts_dir / "metrics_report.json").write_text(
        json.dumps(metrics_report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with (artifacts_dir / "metrics_report.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "model", "accuracy", "precision", "recall", "f1_score",
                "roc_auc", "pr_auc", "train_loss", "val_loss", "generalization_gap",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

def plot_confusion_matrix(cm, labels, save_path):
    if not HAS_MATPLOTLIB: return
    fig, ax = plt.subplots(figsize=(10, 8))
    im = ax.imshow(cm, interpolation="nearest", cmap=plt.cm.Blues); plt.colorbar(im, ax=ax)
    ax.set(xticks=np.arange(len(labels)), yticks=np.arange(len(labels)),
           xticklabels=labels, yticklabels=labels, ylabel="True", xlabel="Predicted", title="Confusion Matrix (best model)")
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")
    thresh = cm.max() / 2.0
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center",
                    color="white" if cm[i, j] > thresh else "black", fontsize=7)
    fig.tight_layout(); fig.savefig(str(save_path), dpi=120); plt.close(fig)

def plot_training_histories(results, plots_dir):
    if not HAS_MATPLOTLIB: return
    plots_dir.mkdir(parents=True, exist_ok=True)
    if not results:
        return
    cmap = plt.get_cmap("tab10")
    colors = [cmap(i % 10) for i in range(len(results))]
    fig, ax = plt.subplots(figsize=(10, 6))
    for r, c in zip(results, colors): ax.plot(r["history"]["train_loss"], label=r["model_name"].upper(), color=c)
    ax.set(title="Training Loss", xlabel="Epoch", ylabel="Loss"); ax.legend(); fig.tight_layout()
    fig.savefig(str(plots_dir / "training_loss.png"), dpi=120); plt.close(fig)
    fig, ax = plt.subplots(figsize=(10, 6))
    for r, c in zip(results, colors): ax.plot(r["history"]["val_loss"], label=r["model_name"].upper(), color=c)
    ax.set(title="Validation Loss", xlabel="Epoch", ylabel="Loss"); ax.legend(); fig.tight_layout()
    fig.savefig(str(plots_dir / "validation_loss.png"), dpi=120); plt.close(fig)
    labels = [r["model_name"].upper() for r in results]
    roc_aucs = [r["metrics"].get("roc_auc", 0) for r in results]
    pr_aucs = [r["metrics"].get("pr_auc", 0) for r in results]
    accuracies = [r["metrics"]["accuracy"] for r in results]
    f1s = [r["metrics"]["f1_score"] for r in results]
    fig, ax = plt.subplots(figsize=(8, 5)); ax.bar(labels, roc_aucs, color=colors[:len(labels)])
    ax.set(title="ROC-AUC Comparison (Macro)", ylabel="ROC-AUC", ylim=(0, 1)); fig.tight_layout()
    fig.savefig(str(plots_dir / "roc_auc_comparison.png"), dpi=120); plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 5)); ax.bar(labels, pr_aucs, color=colors[:len(labels)])
    ax.set(title="PR-AUC Comparison (Macro)", ylabel="PR-AUC", ylim=(0, 1)); fig.tight_layout()
    fig.savefig(str(plots_dir / "pr_auc_comparison.png"), dpi=120); plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(labels, f1s, color=colors[:len(labels)])
    ax.set(title="Macro-F1 Comparison", ylabel="Macro-F1", ylim=(0, 1)); fig.tight_layout()
    fig.savefig(str(plots_dir / "macro_f1_comparison.png"), dpi=120); plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(labels, accuracies, color=colors[:len(labels)])
    ax.set(title="Accuracy Comparison", ylabel="Accuracy", ylim=(0, 1)); fig.tight_layout()
    fig.savefig(str(plots_dir / "accuracy_comparison.png"), dpi=120); plt.close(fig)

    gaps = [r["metrics"].get("generalization_gap", 0) for r in results]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(labels, gaps, color=colors[:len(labels)])
    ax.set(title="Generalization Gap Comparison", ylabel="Val Loss - Train Loss")
    fig.tight_layout()
    fig.savefig(str(plots_dir / "generalization_gap_comparison.png"), dpi=120); plt.close(fig)

    train_losses = [r["metrics"].get("train_loss", 0) for r in results]
    val_losses = [r["metrics"].get("val_loss", 0) for r in results]
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(train_losses, val_losses, c=colors[:len(labels)], s=90)
    for i, label in enumerate(labels):
        ax.annotate(label, (train_losses[i], val_losses[i]), xytext=(6, 4), textcoords="offset points")
    ax.set(title="Train vs Validation Loss", xlabel="Train Loss", ylabel="Validation Loss")
    fig.tight_layout()
    fig.savefig(str(plots_dir / "train_vs_val_loss_scatter.png"), dpi=120); plt.close(fig)

    metric_names = ["Accuracy", "Macro-F1", "ROC-AUC", "PR-AUC"]
    matrix = np.array([
        [r["metrics"].get("accuracy", 0), r["metrics"].get("f1_score", 0), r["metrics"].get("roc_auc", 0), r["metrics"].get("pr_auc", 0)]
        for r in results
    ], dtype=np.float32)
    fig, ax = plt.subplots(figsize=(10, 5))
    im = ax.imshow(matrix, cmap="YlGnBu", aspect="auto", vmin=0, vmax=1)
    ax.set_xticks(np.arange(len(metric_names)))
    ax.set_xticklabels(metric_names)
    ax.set_yticks(np.arange(len(labels)))
    ax.set_yticklabels(labels)
    ax.set_title("Metric Heatmap")
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            ax.text(j, i, f"{matrix[i, j]:.3f}", ha="center", va="center", color="black", fontsize=8)
    plt.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(str(plots_dir / "metric_heatmap.png"), dpi=120)
    plt.close(fig)

    x = np.arange(len(labels)); width = 0.25
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(x - width, accuracies, width, label="Accuracy", color="#4C78A8")
    ax.bar(x, f1s, width, label="Macro-F1", color="#F58518")
    ax.bar(x + width, roc_aucs, width, label="ROC-AUC", color="#54A24B")
    ax.set(title="Model Comparison", ylim=(0, 1)); ax.set_xticks(x); ax.set_xticklabels(labels); ax.legend()
    fig.tight_layout(); fig.savefig(str(plots_dir / "model_comparison_bar.png"), dpi=120); plt.close(fig)