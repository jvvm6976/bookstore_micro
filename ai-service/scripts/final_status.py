#!/usr/bin/env python3
"""Final pipeline status - simple check after all components loaded"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.graph.neo4j_adapter import neo4j_adapter

BASE_DIR = Path(__file__).resolve().parents[1]  # Go up to recommender-ai-service/

# Dataset check
dataset_path = BASE_DIR / "data" / "data_user500.csv"
assert dataset_path.exists(), "Dataset missing"
dataset_ok = True

# Model artifacts check
artifacts = [
    BASE_DIR / "artifacts" / "model_best.pt",
    BASE_DIR / "artifacts" / "all_model_results.json",
    BASE_DIR / "artifacts" / "model_best_summary.json",
]
models_ok = all(a.exists() for a in artifacts)

# Neo4j check
neo4j_ok = neo4j_adapter.available

# Graph stats
if neo4j_ok:
    users = neo4j_adapter.run("MATCH (u:User) RETURN count(u) as c")[0]["c"]
    products = neo4j_adapter.run("MATCH (p:Product) RETURN count(p) as c")[0]["c"]
    rels = neo4j_adapter.run("MATCH ()-[r]->() RETURN count(r) as c")[0]["c"]
    graph_stats = {"users": users, "products": products, "relations": rels}
else:
    graph_stats = {}

status = {
    "✓_dataset": dataset_ok,
    "✓_models": models_ok,
    "✓_neo4j": neo4j_ok,
    "graph_nodes": graph_stats,
    "overall": dataset_ok and models_ok and neo4j_ok
}

print(json.dumps(status, indent=2))
exit(0 if status["overall"] else 1)
