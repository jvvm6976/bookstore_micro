from __future__ import annotations

import os
from pathlib import Path

from .dataset import load_split_data
from .models.bigru_model import BiGRUClassifier
from .train_common import train_classifier, set_seed

NUM_CLASSES = 10


def run(csv_path: str | Path | None = None, seed: int | None = None) -> dict:
    base_dir = Path(__file__).resolve().parents[2]
    data_source = csv_path or os.getenv("AI_TRAINING_CSV")
    if not data_source:
        raise ValueError(
            "Pass csv_path or set AI_TRAINING_CSV to a real training CSV; "
            "generated synthetic AI datasets are no longer kept in this service."
        )
    data_path = Path(data_source)
    artifacts_dir = base_dir / "artifacts"
    run_seed = int(seed if seed is not None else os.getenv("TRAIN_SEED", "42"))
    set_seed(run_seed)
    split_data = load_split_data(data_path, seq_len=12, seed=run_seed)
    feature_dim = split_data.X_train.shape[2]
    model = BiGRUClassifier(input_dim=feature_dim, hidden_dim=64, num_layers=1, num_classes=NUM_CLASSES)
    return train_classifier(model, split_data, "bigru", "bigru", artifacts_dir)


if __name__ == "__main__":
    result = run()
    print(result["metrics"])
