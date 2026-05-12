from __future__ import annotations

import json
from pathlib import Path

from .train_bilstm import run as run_bilstm
from .train_common import plot_training_histories, save_metrics_files
from .train_lstm import run as run_lstm
from .train_rnn import run as run_rnn


def run_all(csv_path: str | Path | None = None) -> list[dict]:
    results = [
        run_rnn(csv_path),
        run_lstm(csv_path),
        run_bilstm(csv_path),
    ]

    base_dir = Path(__file__).resolve().parents[2]
    artifacts_dir = base_dir / "artifacts"
    plots_dir = artifacts_dir / "plots"

    save_metrics_files(results, artifacts_dir)
    plot_training_histories(results, plots_dir)

    with (artifacts_dir / "all_model_results.json").open("w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    return results


if __name__ == "__main__":
    out = run_all()
    print([{r["model_name"]: r["metrics"]} for r in out])
