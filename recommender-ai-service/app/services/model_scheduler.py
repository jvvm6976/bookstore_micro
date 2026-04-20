"""Periodic behavior model training scheduler."""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TRAIN_SCRIPT = PROJECT_ROOT / "scripts" / "train_model.py"


def _interval_seconds() -> int:
    raw = os.getenv("BEHAVIOR_MODEL_TRAIN_INTERVAL_HOURS", "24")
    try:
        hours = max(1, int(raw))
    except ValueError:
        hours = 24
    return hours * 3600


def _train_once() -> bool:
    if not TRAIN_SCRIPT.exists():
        logger.warning("Train script not found: %s", TRAIN_SCRIPT)
        return False
    try:
        logger.info("Starting scheduled behavior model training...")
        result = subprocess.run(
            [sys.executable, str(TRAIN_SCRIPT)],
            cwd=str(PROJECT_ROOT),
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.warning("Behavior training failed (code=%s): %s", result.returncode, result.stderr[-1000:])
            return False
        logger.info("Behavior training completed successfully")
        from .behavior_analysis import behavior_service

        behavior_service.reload_if_updated(force=True)
        return True
    except Exception as exc:
        logger.warning("Behavior training error: %s", exc)
        return False


def start_training_scheduler() -> None:
    """Run a background loop that retrains behavior model periodically."""
    enabled = os.getenv("BEHAVIOR_MODEL_TRAIN_ENABLED", "1").strip().lower() in {"1", "true", "yes"}
    if not enabled:
        logger.info("Behavior model scheduler disabled via BEHAVIOR_MODEL_TRAIN_ENABLED")
        return

    interval = _interval_seconds()
    train_on_start = os.getenv("BEHAVIOR_MODEL_TRAIN_ON_START", "0").strip().lower() in {"1", "true", "yes"}

    def _loop() -> None:
        if train_on_start:
            _train_once()
        while True:
            time.sleep(interval)
            _train_once()

    thread = threading.Thread(target=_loop, name="behavior-model-scheduler", daemon=True)
    thread.start()
    logger.info("Behavior model scheduler started (interval=%ss)", interval)
