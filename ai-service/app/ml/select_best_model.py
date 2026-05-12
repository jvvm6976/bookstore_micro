from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


def choose_best(results: list[dict[str, Any]]) -> dict[str, Any]:
    # Priority: F1-score, then accuracy.
    return sorted(
        results,
        key=lambda r: (r["metrics"]["f1_score"], r["metrics"]["accuracy"]),
        reverse=True,
    )[0]


def run(results: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    base_dir = Path(__file__).resolve().parents[2]
    artifacts_dir = base_dir / "artifacts"

    if results is None:
        src = artifacts_dir / "all_model_results.json"
        if not src.exists():
            from .evaluate_models import run_all

            results = run_all()
        else:
            results = json.loads(src.read_text(encoding="utf-8"))

    best = choose_best(results)

    src_model = Path(best["model_path"])
    dst_model = artifacts_dir / "model_best.pt"
    shutil.copyfile(src_model, dst_model)

    meta = dict(best.get("meta", {}))
    meta["selection_reason"] = (
        "model_best is selected by highest F1-score on test set; "
        "if tied, higher accuracy wins."
    )
    meta["selected_from"] = [r["model_name"] for r in results]

    with (artifacts_dir / "model_best_meta.json").open("w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    summary = {
        "model_best": best["model_name"],
        "model_type": best["model_type"],
        "metrics": best["metrics"],
        "reason": meta["selection_reason"],
    }

    with (artifacts_dir / "model_best_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    return summary


if __name__ == "__main__":
    print(run())
