from __future__ import annotations

import os
from pathlib import Path

from .dataset import load_split_data
from .models.rnn_model import RNNClassifier
from .train_common import train_classifier, set_seed


def run(csv_path: str | Path | None = None, seed: int | None = None) -> dict:
    base_dir = Path(__file__).resolve().parents[2]
    data_path = Path(csv_path) if csv_path else base_dir / "data" / "data_user500.csv"
    artifacts_dir = base_dir / "artifacts"

    run_seed = int(seed if seed is not None else os.getenv("TRAIN_SEED", "42"))

    set_seed(run_seed)
    split_data = load_split_data(data_path, seq_len=12, seed=run_seed)
    model = RNNClassifier(input_dim=6, hidden_dim=64, num_layers=1, num_classes=8)
    return train_classifier(model, split_data, "rnn", "rnn", artifacts_dir)


if __name__ == "__main__":
    result = run()
    print(result["metrics"])
