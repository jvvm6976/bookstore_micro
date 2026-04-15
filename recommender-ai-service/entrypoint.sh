#!/bin/bash
set -e

echo "[AI Service] Running Django migrations..."
python manage.py migrate --noinput 2>&1 || echo "Migration warning (non-fatal)"

echo "[AI Service] Training behavior model (if not exists)..."
if [ ! -f "artifacts/behavior_model.pt" ]; then
    python scripts/train_model.py && echo "Model trained." || echo "Model training skipped."
fi

echo "[AI Service] Starting FastAPI + uvicorn..."
exec uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1 --log-level info
