from __future__ import annotations

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.graph.graph_builder import build_from_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="Load data_user500.csv into the AI-service02 KB graph")
    parser.add_argument("--data", default="data/data_user500.csv", help="Path to dataset CSV")
    parser.add_argument("--clear", action="store_true", help="Delete existing graph before load")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parents[1]
    csv_path = (base_dir / args.data).resolve() if not Path(args.data).is_absolute() else Path(args.data)

    stats = build_from_csv(csv_path, clear_first=args.clear)
    print("Graph load completed:", stats)


if __name__ == "__main__":
    main()
