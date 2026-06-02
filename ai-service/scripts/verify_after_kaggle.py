#!/usr/bin/env python3
"""Verify Kaggle-trained artifacts and runtime integration for recommender-ai-service.

Usage:
  python scripts/verify_after_kaggle.py
  python scripts/verify_after_kaggle.py --check-api
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib import error as url_error
from urllib import request as url_request

BASE_DIR = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = BASE_DIR / "artifacts"

REQUIRED_ARTIFACTS = [
    "model_best.pt",
    "model_best_meta.json",
    "model_best_summary.json",
    "all_runs_metrics_raw.json",
    "all_model_results.json",
    "metrics_report.json",
]

ALLOWED_MODEL_TYPES = {"rnn", "lstm", "bilstm", "gru", "bigru"}


def _http_json(url: str, method: str = "GET", body: dict | None = None) -> tuple[int, dict | list | str]:
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
    except Exception as exc:
        return 0, str(exc)


def verify_artifacts() -> tuple[bool, list[str]]:
    errors: list[str] = []

    for name in REQUIRED_ARTIFACTS:
        if not (ARTIFACTS_DIR / name).exists():
            errors.append(f"Missing artifact: artifacts/{name}")

    meta_path = ARTIFACTS_DIR / "model_best_meta.json"
    summary_path = ARTIFACTS_DIR / "model_best_summary.json"

    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            model_type = str(meta.get("model_type", "")).lower()
            if model_type not in ALLOWED_MODEL_TYPES:
                errors.append(
                    f"model_best_meta.json has unsupported model_type='{model_type}'. "
                    f"Allowed={sorted(ALLOWED_MODEL_TYPES)}"
                )
            required_meta_keys = [
                "feature_dim",
                "num_classes",
                "seq_len",
                "category_to_id",
                "sub_category_to_id",
            ]
            missing_meta_keys = [k for k in required_meta_keys if k not in meta]
            if missing_meta_keys:
                errors.append(f"model_best_meta.json missing keys: {missing_meta_keys}")
        except Exception as exc:
            errors.append(f"Cannot parse model_best_meta.json: {exc}")

    if summary_path.exists():
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            best = str(summary.get("model_best", "")).lower()
            if best not in ALLOWED_MODEL_TYPES:
                errors.append(
                    f"model_best_summary.json has invalid model_best='{best}'. "
                    f"Allowed={sorted(ALLOWED_MODEL_TYPES)}"
                )
        except Exception as exc:
            errors.append(f"Cannot parse model_best_summary.json: {exc}")

    return len(errors) == 0, errors


def verify_api() -> tuple[bool, list[str]]:
    errors: list[str] = []

    code, health = _http_json("http://localhost:8009/health")
    if code != 200:
        errors.append(f"AI health check failed: HTTP {code}, payload={health}")
        return False, errors

    if not isinstance(health, dict):
        errors.append("AI health payload is not JSON object")
        return False, errors

    code, rec = _http_json("http://localhost:8009/api/v1/recommend/1")
    if code != 200:
        errors.append(f"Recommend API failed: HTTP {code}, payload={rec}")

    code, chat = _http_json(
        "http://localhost:8000/api/v1/chat",
        method="POST",
        body={"message": "goi y san pham cho toi", "customer_id": 1},
    )
    if code != 200:
        errors.append(f"Chat API failed: HTTP {code}, payload={chat}")

    return len(errors) == 0, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Kaggle artifacts and runtime integration")
    parser.add_argument("--check-api", action="store_true", help="Also verify /health, /recommend, /chat endpoints")
    args = parser.parse_args()

    ok_artifacts, artifact_errors = verify_artifacts()

    result = {
        "artifacts_ok": ok_artifacts,
        "artifacts_errors": artifact_errors,
        "api_ok": None,
        "api_errors": [],
    }

    if args.check_api:
        ok_api, api_errors = verify_api()
        result["api_ok"] = ok_api
        result["api_errors"] = api_errors

    print(json.dumps(result, ensure_ascii=False, indent=2))

    if not ok_artifacts:
        return 1
    if args.check_api and result["api_ok"] is False:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
