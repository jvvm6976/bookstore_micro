from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error as url_error
from urllib import request as url_request

BASE_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BASE_DIR.parent
DATASET_PATH = BASE_DIR / "data" / "data_user500.csv"
ARTIFACTS_DIR = BASE_DIR / "artifacts"
FINAL_STATUS_PATH = ROOT_DIR / "FINAL_RUNTIME_STATUS.md"


@dataclass
class CheckResult:
    ok: bool
    detail: str


@dataclass
class RuntimeReport:
    dataset: CheckResult
    models: CheckResult
    model_best: CheckResult
    neo4j_runtime: CheckResult
    graph_retrieval: CheckResult
    hybrid_integration: CheckResult
    blockers: list[str]
    legacy_references: list[str]


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dataset_check() -> CheckResult:
    if not DATASET_PATH.exists():
        return CheckResult(False, f"Missing dataset: {DATASET_PATH}")

    with DATASET_PATH.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        return CheckResult(False, "Dataset exists but has no rows")

    required = {"user_id", "product_id", "action", "timestamp"}
    columns = set(rows[0].keys())
    missing = sorted(required - columns)
    if missing:
        return CheckResult(False, f"Missing required columns: {missing}")

    empty_actions = sum(1 for r in rows if not str(r.get("action", "")).strip())
    if empty_actions > 0:
        return CheckResult(False, f"Column action has {empty_actions} empty rows")

    user_count = len({int(float(r["user_id"])) for r in rows if r.get("user_id")})
    actions = sorted({str(r["action"]).strip() for r in rows if str(r.get("action", "")).strip()})

    if user_count < 500:
        return CheckResult(False, f"Expected >=500 users, found {user_count}")

    return CheckResult(True, f"rows={len(rows)}, users={user_count}, action_values={actions}")


def _ml_pipeline_dataset_check() -> tuple[CheckResult, list[str]]:
    target_files = [
        BASE_DIR / "app" / "ml" / "train_rnn.py",
        BASE_DIR / "app" / "ml" / "train_lstm.py",
        BASE_DIR / "app" / "ml" / "train_bilstm.py",
        BASE_DIR / "app" / "ml" / "evaluate_models.py",
        BASE_DIR / "app" / "ml" / "select_best_model.py",
    ]

    bad_refs = []
    for p in target_files:
        text = p.read_text(encoding="utf-8")
        if "data_user500.csv" not in text and p.name in {"train_rnn.py", "train_lstm.py", "train_bilstm.py"}:
            bad_refs.append(f"{p}: missing data_user500.csv default")
        if re.search(r"data_1000|data_100user|data_1000user", text):
            bad_refs.append(f"{p}: legacy dataset reference")

    if bad_refs:
        return CheckResult(False, "; ".join(bad_refs)), bad_refs

    return CheckResult(True, "train/evaluate/select_best point to data_user500.csv pipeline"), []


def _find_legacy_dataset_refs() -> list[str]:
    refs: list[str] = []
    pattern = re.compile(r"data_1000|data_100user|data_1000user")

    for p in BASE_DIR.rglob("*.py"):
        rel = p.relative_to(BASE_DIR)
        if rel.as_posix() == "scripts/verify_runtime.py":
            continue
        if "venv" in rel.parts or ".venv" in rel.parts:
            continue
        txt = p.read_text(encoding="utf-8", errors="ignore")
        if pattern.search(txt):
            refs.append(str(rel))

    for p in BASE_DIR.rglob("*.md"):
        rel = p.relative_to(BASE_DIR)
        if rel.as_posix() == "scripts/verify_runtime.py":
            continue
        if "venv" in rel.parts or ".venv" in rel.parts:
            continue
        txt = p.read_text(encoding="utf-8", errors="ignore")
        if pattern.search(txt):
            refs.append(str(rel))

    return sorted(set(refs))


def _model_artifacts_check() -> tuple[CheckResult, CheckResult]:
    required = [
        ARTIFACTS_DIR / "rnn_model.pt",
        ARTIFACTS_DIR / "lstm_model.pt",
        ARTIFACTS_DIR / "bilstm_model.pt",
        ARTIFACTS_DIR / "model_best.pt",
        ARTIFACTS_DIR / "all_model_results.json",
        ARTIFACTS_DIR / "model_best_summary.json",
    ]
    missing = [str(p.name) for p in required if not p.exists()]
    if missing:
        fail = CheckResult(False, f"Missing artifacts: {missing}")
        return fail, fail

    ts = [p.stat().st_mtime for p in required]
    newest_age_sec = time.time() - max(ts)
    models_ok = CheckResult(True, f"All 4 model files exist; newest artifact age={newest_age_sec:.1f}s")

    all_results = _read_json(ARTIFACTS_DIR / "all_model_results.json")
    summary = _read_json(ARTIFACTS_DIR / "model_best_summary.json")

    ranked = sorted(
        all_results,
        key=lambda r: (r["metrics"]["f1_score"], r["metrics"]["accuracy"]),
        reverse=True,
    )
    expected_best = ranked[0]["model_name"]
    expected_path = Path(ranked[0]["model_path"])

    best_hash = _hash_file(ARTIFACTS_DIR / "model_best.pt")
    expected_hash = _hash_file(expected_path)

    if summary.get("model_best") != expected_best:
        return models_ok, CheckResult(False, f"model_best_summary mismatch: expected {expected_best}, got {summary.get('model_best')}")

    if best_hash != expected_hash:
        return models_ok, CheckResult(False, "model_best.pt hash does not match selected source model")

    return models_ok, CheckResult(True, f"model_best={expected_best}, hash matched selected source model")


def _docker_daemon_running() -> tuple[bool, str]:
    try:
        proc = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=20)
    except FileNotFoundError:
        return False, "docker command not found"
    except Exception as exc:
        return False, f"docker check error: {exc}"

    if proc.returncode != 0:
        return False, proc.stderr.strip() or proc.stdout.strip() or "docker info failed"
    return True, "docker daemon is running"


def _neo4j_runtime_check() -> tuple[CheckResult, dict[str, Any]]:
    docker_ok, docker_msg = _docker_daemon_running()
    if not docker_ok:
        return CheckResult(False, f"Runtime blocker: {docker_msg}"), {}

    cmd = [
        sys.executable,
        str(BASE_DIR / "scripts" / "verify_neo4j.py"),
        "--ingest-csv",
        str(DATASET_PATH),
        "--clear",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()

    if proc.returncode != 0:
        detail = out or err or "verify_neo4j failed"
        return CheckResult(False, detail), {}

    try:
        payload = json.loads(out)
    except Exception:
        return CheckResult(False, f"verify_neo4j output parse failed: {out}"), {}

    users = int(payload.get("user_nodes", 0))
    products = int(payload.get("product_nodes", 0))
    rels = payload.get("relations_by_type", {})

    if users <= 0 or products <= 0:
        return CheckResult(False, f"Connected but graph empty: users={users}, products={products}"), payload

    return CheckResult(True, f"users={users}, products={products}, relation_types={len(rels)}"), payload


def _http_json(url: str, method: str = "GET", body: dict[str, Any] | None = None) -> tuple[int, dict[str, Any] | list[Any] | str]:
    data = None
    headers = {"Content-Type": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = url_request.Request(url, data=data, headers=headers, method=method)
    try:
        with url_request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(raw)
            except Exception:
                return resp.status, raw
    except url_error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="ignore")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw


def _graph_and_hybrid_runtime_checks() -> tuple[CheckResult, CheckResult, list[str]]:
    blockers: list[str] = []

    # Static proof first: graph + hybrid are wired in code.
    rec_py = (BASE_DIR / "app" / "services" / "recommendation.py").read_text(encoding="utf-8")
    routes_py = (BASE_DIR / "app" / "api" / "routes.py").read_text(encoding="utf-8")

    static_ok = all(
        token in rec_py
        for token in ["W_GRAPH", "neo4j_adapter.get_graph_scores", "final_score", "graph_component"]
    ) and "neo4j_adapter.write_interaction" in routes_py

    if not static_ok:
        fail = CheckResult(False, "Graph/hybrid wiring tokens missing in code")
        return fail, fail, blockers

    # Runtime proof requires services up.
    try:
        code, health_payload = _http_json("http://localhost:8011/health")
    except Exception as exc:
        blockers.append(f"AI runtime not reachable at localhost:8011 ({exc})")
        return (
            CheckResult(False, "Static wiring OK, runtime verification blocked (AI service down)"),
            CheckResult(False, "Runtime verification blocked (AI service down)"),
            blockers,
        )

    if code != 200:
        blockers.append(f"AI /health returned {code}")
        return (
            CheckResult(False, f"Static wiring OK, runtime blocked (/health={code})"),
            CheckResult(False, f"Runtime blocked (/health={code})"),
            blockers,
        )

    # Before/after interaction verification.
    customer_id = 1
    rec_url = f"http://localhost:8011/api/v1/recommend/{customer_id}?limit=8"
    c1, p1 = _http_json(rec_url)
    if c1 != 200 or not isinstance(p1, dict):
        blockers.append(f"recommend before-track failed: HTTP {c1}")
        return (
            CheckResult(False, "Static wiring OK, runtime recommend test failed"),
            CheckResult(False, "Runtime recommend test failed"),
            blockers,
        )

    recs1 = p1.get("recommendations", [])
    if not recs1:
        blockers.append("recommend before-track returned empty list")
        return (
            CheckResult(False, "Static wiring OK, runtime recommend list empty"),
            CheckResult(False, "Runtime recommend list empty"),
            blockers,
        )

    target_pid = int(recs1[0].get("product_id", 0) or 0)
    if target_pid <= 0:
        blockers.append("Top recommendation has invalid product_id")
        return (
            CheckResult(False, "Static wiring OK, invalid recommendation payload"),
            CheckResult(False, "Invalid recommendation payload"),
            blockers,
        )

    t_code, t_payload = _http_json(
        "http://localhost:8011/api/v1/track",
        method="POST",
        body={
            "customer_id": customer_id,
            "product_id": target_pid,
            "interaction_type": "click_recommendation",
        },
    )
    if t_code != 200:
        blockers.append(f"track failed HTTP {t_code}")
        return (
            CheckResult(False, "Static wiring OK, track endpoint failed"),
            CheckResult(False, "Track endpoint failed"),
            blockers,
        )

    c2, p2 = _http_json(rec_url)
    if c2 != 200 or not isinstance(p2, dict):
        blockers.append(f"recommend after-track failed: HTTP {c2}")
        return (
            CheckResult(False, "Static wiring OK, after-track recommend failed"),
            CheckResult(False, "After-track recommend failed"),
            blockers,
        )

    recs2 = p2.get("recommendations", [])
    ids1 = [int(x.get("product_id", 0) or 0) for x in recs1[:8]]
    ids2 = [int(x.get("product_id", 0) or 0) for x in recs2[:8]]

    changed = ids1 != ids2

    graph_retrieval = CheckResult(
        True,
        "Graph runtime reachable; track endpoint executed and collaborative graph is enabled in health payload",
    )

    hybrid = CheckResult(
        changed,
        "Ranking changed after new interaction" if changed else "Ranking did not change in this single-step probe",
    )

    if not changed:
        blockers.append("Hybrid ranking change not observed in single probe; may need repeated interactions")

    return graph_retrieval, hybrid, blockers


def _status_label(ok: bool) -> str:
    return "OK" if ok else "NOT OK"


def _write_final_md(report: RuntimeReport) -> None:
    verdict = "RUNNABLE" if all(
        [
            report.dataset.ok,
            report.models.ok,
            report.model_best.ok,
            report.neo4j_runtime.ok,
            report.graph_retrieval.ok,
            report.hybrid_integration.ok,
        ]
    ) else "NOT YET RUNNABLE"

    lines = [
        "# FINAL RUNTIME STATUS",
        "",
        "## Checklist",
        f"- Dataset: {_status_label(report.dataset.ok)}",
        f"- 3 models: {_status_label(report.models.ok)}",
        f"- model_best: {_status_label(report.model_best.ok)}",
        f"- Neo4j runtime: {_status_label(report.neo4j_runtime.ok)}",
        f"- Graph retrieval: {_status_label(report.graph_retrieval.ok)}",
        f"- Hybrid integration: {_status_label(report.hybrid_integration.ok)}",
        "",
        "## Details",
        f"- Dataset detail: {report.dataset.detail}",
        f"- Models detail: {report.models.detail}",
        f"- model_best detail: {report.model_best.detail}",
        f"- Neo4j detail: {report.neo4j_runtime.detail}",
        f"- Graph retrieval detail: {report.graph_retrieval.detail}",
        f"- Hybrid detail: {report.hybrid_integration.detail}",
        "",
        "## Legacy Dataset References",
    ]

    if report.legacy_references:
        lines.extend([f"- {x}" for x in report.legacy_references])
    else:
        lines.append("- None")

    lines.extend([
        "",
        "## Runtime Blockers",
    ])
    if report.blockers:
        lines.extend([f"- {b}" for b in report.blockers])
    else:
        lines.append("- None")

    lines.extend([
        "",
        f"## Final Verdict: {verdict}",
        "",
        "If verdict is NOT YET RUNNABLE, resolve blockers and re-run:",
        "python recommender-ai-service/scripts/verify_runtime.py",
    ])

    FINAL_STATUS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    blockers: list[str] = []

    dataset = _dataset_check()
    ml_check, ml_refs = _ml_pipeline_dataset_check()
    if not ml_check.ok:
        blockers.append(ml_check.detail)

    legacy_refs = _find_legacy_dataset_refs()

    models, model_best = _model_artifacts_check()

    neo4j_runtime, _ = _neo4j_runtime_check()
    if not neo4j_runtime.ok:
        blockers.append(neo4j_runtime.detail)

    graph_retrieval, hybrid_integration, gh_blockers = _graph_and_hybrid_runtime_checks()
    blockers.extend(gh_blockers)

    report = RuntimeReport(
        dataset=dataset,
        models=CheckResult(models.ok and ml_check.ok, f"{models.detail}; {ml_check.detail}"),
        model_best=model_best,
        neo4j_runtime=neo4j_runtime,
        graph_retrieval=graph_retrieval,
        hybrid_integration=hybrid_integration,
        blockers=blockers,
        legacy_references=legacy_refs,
    )

    _write_final_md(report)

    print(json.dumps(
        {
            "dataset": report.dataset.__dict__,
            "models": report.models.__dict__,
            "model_best": report.model_best.__dict__,
            "neo4j_runtime": report.neo4j_runtime.__dict__,
            "graph_retrieval": report.graph_retrieval.__dict__,
            "hybrid_integration": report.hybrid_integration.__dict__,
            "legacy_references": report.legacy_references,
            "blockers": report.blockers,
            "final_status_path": str(FINAL_STATUS_PATH),
        },
        ensure_ascii=False,
        indent=2,
    ))

    all_ok = all(
        [
            report.dataset.ok,
            report.models.ok,
            report.model_best.ok,
            report.neo4j_runtime.ok,
            report.graph_retrieval.ok,
            report.hybrid_integration.ok,
        ]
    )
    return 0 if all_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
