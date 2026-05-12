from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


def _relation_counts(driver) -> dict[str, int]:
    with driver.session() as session:
        rows = session.run(
            """
            MATCH ()-[r]->()
            RETURN type(r) AS rel, count(r) AS cnt
            ORDER BY cnt DESC
            """
        )
        return {r["rel"]: int(r["cnt"]) for r in rows}


def _basic_counts(driver) -> dict[str, int]:
    with driver.session() as session:
        users = session.run("MATCH (u:User) RETURN count(u) AS c").single()["c"]
        products = session.run("MATCH (p:Product) RETURN count(p) AS c").single()["c"]
    return {"user_nodes": int(users), "product_nodes": int(products)}


def _try_connect(uri: str, user: str, password: str):
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(uri, auth=(user, password))
    driver.verify_connectivity()
    return driver


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Neo4j runtime and optional ingest from data_user500.csv")
    parser.add_argument("--uri", default=os.getenv("NEO4J_URI", ""), help="Neo4j bolt URI")
    parser.add_argument("--user", default=os.getenv("NEO4J_USER", "neo4j"), help="Neo4j username")
    parser.add_argument("--password", default=os.getenv("NEO4J_PASSWORD", "neo4j_password"), help="Neo4j password")
    parser.add_argument("--ingest-csv", default="", help="Optional CSV path to ingest before verification")
    parser.add_argument("--clear", action="store_true", help="Clear graph before ingest")
    args = parser.parse_args()

    uris = []
    if args.uri:
        uris.append(args.uri)
    uris.extend(["bolt://localhost:7687", "bolt://neo4j:7687"])

    driver = None
    used_uri = None
    errors: list[str] = []

    for uri in uris:
        if uri in (u for u in [used_uri] if u):
            continue
        try:
            driver = _try_connect(uri, args.user, args.password)
            used_uri = uri
            break
        except Exception as exc:
            errors.append(f"{uri}: {exc}")

    if driver is None:
        print(json.dumps(
            {
                "neo4j_runtime_ok": False,
                "blocker": "Neo4j is unreachable. Start Docker + neo4j service before runtime verification.",
                "attempts": errors,
            },
            ensure_ascii=False,
            indent=2,
        ))
        return 2

    ingest_stats = None
    if args.ingest_csv:
        from app.graph.graph_builder import build_from_csv

        ingest_stats = build_from_csv(args.ingest_csv, clear_first=args.clear)

    summary = {
        "neo4j_runtime_ok": True,
        "uri": used_uri,
        "ingest": ingest_stats,
        **_basic_counts(driver),
        "relations_by_type": _relation_counts(driver),
    }

    driver.close()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
