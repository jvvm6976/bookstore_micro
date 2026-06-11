from __future__ import annotations

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

# Simplified 8 action types for the dataset pipeline
BEHAVIORS = [
    "search",
    "view",
    "add_to_cart",
    "purchase",
    "rate_product",
    "wishlist",
    "remove_from_cart",
    "click",
]

# Realistic action transition probabilities (order matches BEHAVIORS)
ACTION_TRANSITIONS = {
    "search": [0.10, 0.45, 0.08, 0.03, 0.01, 0.10, 0.02, 0.21],
    "view": [0.10, 0.15, 0.27, 0.08, 0.01, 0.18, 0.06, 0.15],
    "add_to_cart": [0.05, 0.12, 0.12, 0.30, 0.03, 0.12, 0.20, 0.06],
    "purchase": [0.03, 0.17, 0.05, 0.05, 0.50, 0.08, 0.02, 0.10],
    "rate_product": [0.07, 0.26, 0.10, 0.05, 0.08, 0.14, 0.05, 0.25],
    "wishlist": [0.06, 0.24, 0.20, 0.07, 0.01, 0.20, 0.08, 0.14],
    "remove_from_cart": [0.05, 0.27, 0.22, 0.08, 0.01, 0.10, 0.07, 0.20],
    "click": [0.08, 0.38, 0.15, 0.08, 0.01, 0.08, 0.02, 0.20],
}


def _pick_next_action(rng: random.Random, current_action: str) -> str:
    """Select next action based on transition probabilities."""
    probs = ACTION_TRANSITIONS[current_action]
    return rng.choices(BEHAVIORS, weights=probs, k=1)[0]


def generate(seed: int = 42, n_users: int = 500) -> list[dict]:
    """Generate 500-user behavior dataset with 8 action types."""
    rng = random.Random(seed)
    base_time = datetime(2026, 1, 1, 8, 0, 0)
    rows: list[dict] = []

    for user_id in range(1, n_users + 1):
        n_steps = rng.randint(14, 28)
        current_action = "search"
        current_time = base_time + timedelta(days=rng.randint(0, 80), minutes=rng.randint(0, 120))

        for step in range(1, n_steps + 1):
            product_id = rng.randint(1, 1800)
            event_time = (current_time + timedelta(minutes=step * rng.randint(2, 10))).isoformat()

            rows.append(
                {
                    "user_id": user_id,
                    "product_id": product_id,
                    "action": current_action,
                    "timestamp": event_time,
                }
            )

            current_action = _pick_next_action(rng, current_action)

    return rows


def save(rows: list[dict], output_csv: Path, sample_csv: Path) -> None:
    """Save dataset to CSV files."""
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["user_id", "product_id", "action", "timestamp"]

    with output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Save first 20 rows as sample
    with sample_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows[:20])


def run(seed: int = 42) -> tuple[Path, Path]:
    """Generate and save dataset."""
    base_dir = Path(__file__).resolve().parents[1]
    data_dir = base_dir / "data"
    out = data_dir / "data_user500.csv"
    sample = data_dir / "data_user500_sample20.csv"

    rows = generate(seed=seed, n_users=500)
    save(rows, out, sample)
    return out, sample


if __name__ == "__main__":
    out, sample = run()
    print(f"✓ Generated dataset: {out} ({len(open(out).readlines()) - 1} rows)")
    print(f"✓ Generated sample: {sample}")
