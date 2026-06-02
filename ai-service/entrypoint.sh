#!/bin/bash
set -e

echo "[AI Service] Running Django migrations..."
python manage.py migrate --noinput 2>&1 || echo "Migration warning (non-fatal)"

echo "[AI Service] Checking Kaggle-trained model artifacts..."
if [ ! -f "artifacts/model_best.pt" ] || [ ! -f "artifacts/model_best_meta.json" ]; then
    echo "[AI Service] Kaggle model artifacts are missing; recommendation inference will run without model scoring."
fi

echo "[AI Service] Loading KB + FAISS index..."
python manage.py shell -c "
from app.services.kb_ingestion import kb_service
from app.services.rag_retrieval import rag_service
c = kb_service.load_from_disk()
ok = rag_service.load_index()
if c <= 0:
    c = kb_service.reindex()
    ok = False
if not ok and c > 0:
    rag_service.build_index()
    ok = True
print(f'KB entries: {c}, faiss_loaded: {ok}')
" || echo "KB/FAISS load warning (non-fatal)"

echo "[AI Service] Starting Django API server..."
exec python manage.py runserver 0.0.0.0:8000
