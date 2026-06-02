#!/usr/bin/env python3
"""Apply Kaggle-trained artifacts into recommender-ai-service runtime folders.

Usage:
  python scripts/apply_kaggle_artifacts.py --source /path/to/downloaded/artifacts
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


REQUIRED_FILES = [
    "model_best.pt",
    "model_best_meta.json",
    "model_best_summary.json",
    "all_runs_metrics_raw.json",
    "all_model_results.json",
    "metrics_report.json",
]


def copy_if_exists(src: Path, dst: Path) -> bool:
    if not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Copy Kaggle artifacts into runtime artifact folders")
    parser.add_argument("--source", required=True, help="Path to downloaded Kaggle artifacts folder")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parents[1]
    source = Path(args.source).resolve()
    target_artifacts = base_dir / "artifacts"
    target_artifacts_final = base_dir / "artifacts_final"

    if not source.exists() or not source.is_dir():
        raise FileNotFoundError(f"Source folder not found: {source}")

    missing = [name for name in REQUIRED_FILES if not (source / name).exists()]
    if missing:
        raise FileNotFoundError(f"Missing required files in source: {missing}")

    copied = []
    for name in REQUIRED_FILES:
        src = source / name
        if copy_if_exists(src, target_artifacts / name):
            copied.append(str(target_artifacts / name))
        if copy_if_exists(src, target_artifacts_final / name):
            copied.append(str(target_artifacts_final / name))

    # Copy plots if available.
    source_plots = source / "plots"
    if source_plots.exists() and source_plots.is_dir():
        target_plots = target_artifacts / "plots"
        target_plots_final = target_artifacts_final / "plots"
        target_plots.mkdir(parents=True, exist_ok=True)
        target_plots_final.mkdir(parents=True, exist_ok=True)
        for p in source_plots.glob("*.png"):
            shutil.copy2(p, target_plots / p.name)
            shutil.copy2(p, target_plots_final / p.name)
        print(f"Copied plot images to {target_plots} and {target_plots_final}")

    print("Copied files:")
    for p in copied:
        print(f"  - {p}")

    print("Done. Restart recommender-ai-service to load new model_best artifacts.")


if __name__ == "__main__":
    main()
