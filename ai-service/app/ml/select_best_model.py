"""
Best model selection — scientific criteria:
  Primary  : highest avg_macro_f1
  Secondary: avg_pr_auc, avg_roc_auc, lower generalization_gap
No hardcoding — winner is determined purely from aggregated run metrics.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def aggregate_runs(all_runs: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Group runs by model name and compute averages."""
    from collections import defaultdict
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for run in all_runs:
        groups[run["model_name"]].append(run.get("metrics", {}))

    summary: dict[str, dict[str, float]] = {}
    for model, metrics_list in groups.items():
        summary[model] = {
            "avg_accuracy":           round(_avg([m.get("accuracy", 0) for m in metrics_list]), 6),
            "avg_precision":          round(_avg([m.get("precision", 0) for m in metrics_list]), 6),
            "avg_recall":             round(_avg([m.get("recall", 0) for m in metrics_list]), 6),
            "avg_macro_f1":           round(_avg([m.get("f1_score", 0) for m in metrics_list]), 6),
            "avg_roc_auc":            round(_avg([m.get("roc_auc", 0) for m in metrics_list]), 6),
            "avg_pr_auc":             round(_avg([m.get("pr_auc", 0) for m in metrics_list]), 6),
            "avg_train_loss":         round(_avg([m.get("train_loss", 0) for m in metrics_list]), 6),
            "avg_val_loss":           round(_avg([m.get("val_loss", 0) for m in metrics_list]), 6),
            "avg_generalization_gap": round(_avg([m.get("generalization_gap", 0) for m in metrics_list]), 6),
            "num_runs":               len(metrics_list),
        }
    return summary


def choose_best(summary: dict[str, dict[str, float]]) -> tuple[str, str]:
    """
    Sort key (descending):
      1. avg_macro_f1
      2. avg_pr_auc
      3. avg_roc_auc
      4. -avg_generalization_gap  (lower gap is better)
    Returns (best_model_name, reason_string).
    """
    ranked = sorted(
        summary.items(),
        key=lambda kv: (
            kv[1]["avg_macro_f1"],
            kv[1]["avg_pr_auc"],
            kv[1]["avg_roc_auc"],
            -kv[1]["avg_generalization_gap"],
        ),
        reverse=True,
    )
    best_name, best_stats = ranked[0]

    reason_parts = [
        f"Selected '{best_name}' as best_model.",
        f"Primary criterion: highest avg_macro_f1={best_stats['avg_macro_f1']:.4f}.",
    ]
    # Check if primary criterion was decisive
    top_f1 = best_stats["avg_macro_f1"]
    tied = [n for n, s in ranked[1:] if abs(s["avg_macro_f1"] - top_f1) < 1e-4]
    if tied:
        reason_parts.append(
            f"Tie-broken by avg_pr_auc={best_stats['avg_pr_auc']:.4f}, "
            f"avg_roc_auc={best_stats['avg_roc_auc']:.4f}, "
            f"generalization_gap={best_stats['avg_generalization_gap']:.4f}."
        )
    else:
        reason_parts.append(
            f"avg_pr_auc={best_stats['avg_pr_auc']:.4f}, "
            f"avg_roc_auc={best_stats['avg_roc_auc']:.4f}, "
            f"generalization_gap={best_stats['avg_generalization_gap']:.4f}."
        )

    return best_name, " ".join(reason_parts)


def run(all_runs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    base_dir = Path(__file__).resolve().parents[2]
    artifacts_dir = base_dir / "artifacts"

    if all_runs is None:
        src = artifacts_dir / "all_runs_metrics_raw.json"
        if src.exists():
            all_runs = json.loads(src.read_text(encoding="utf-8"))
        else:
            raise FileNotFoundError(
                "all_runs_metrics_raw.json not found. Run the Kaggle training pipeline or copy Kaggle artifacts first."
            )

    summary = aggregate_runs(all_runs)
    best_name, reason = choose_best(summary)

    # Copy best model weights
    src_model = artifacts_dir / f"{best_name}_model.pt"
    dst_model = artifacts_dir / "model_best.pt"
    if src_model.exists():
        shutil.copyfile(src_model, dst_model)

    # Copy best meta and patch it
    src_meta = artifacts_dir / f"{best_name}_model_meta.json"
    dst_meta = artifacts_dir / "model_best_meta.json"
    if src_meta.exists():
        meta = json.loads(src_meta.read_text(encoding="utf-8"))
        meta["selection_reason"] = reason
        meta["selected_from"] = list(summary.keys())
        dst_meta.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    best_summary = {
        "model_best": best_name,
        "model_type": best_name,
        "avg_metrics": summary[best_name],
        "all_models_summary": summary,
        "reason": reason,
    }
    (artifacts_dir / "model_best_summary.json").write_text(
        json.dumps(best_summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return best_summary


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2, ensure_ascii=False))
