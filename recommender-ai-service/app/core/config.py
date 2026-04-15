"""Central configuration via environment variables."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ── Service URLs ──────────────────────────────────────────────────────────────
BOOK_SERVICE_URL     = os.getenv("BOOK_SERVICE_URL",     "http://book-service:8000")
CATALOG_SERVICE_URL  = os.getenv("CATALOG_SERVICE_URL",  "http://catalog-service:8000")
CUSTOMER_SERVICE_URL = os.getenv("CUSTOMER_SERVICE_URL", "http://customer-service:8000")
ORDER_SERVICE_URL    = os.getenv("ORDER_SERVICE_URL",    "http://order-service:8000")
COMMENT_SERVICE_URL  = os.getenv("COMMENT_SERVICE_URL",  "http://comment-rate-service:8000")
SHIP_SERVICE_URL     = os.getenv("SHIP_SERVICE_URL",     "http://ship-service:8000")
PAY_SERVICE_URL      = os.getenv("PAY_SERVICE_URL",      "http://pay-service:8000")

# ── DB ────────────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:root@db-postgres:5432/bookstore_recommender",
)

# ── AI / Model ────────────────────────────────────────────────────────────────
ARTIFACTS_DIR   = Path(os.getenv("ARTIFACTS_DIR",   str(BASE_DIR / "artifacts")))
FAISS_INDEX_PATH = ARTIFACTS_DIR / "kb_faiss.index"
FAISS_META_PATH  = ARTIFACTS_DIR / "kb_meta.json"
MODEL_PATH       = ARTIFACTS_DIR / "behavior_model.pt"
EMBED_DIM        = int(os.getenv("EMBED_DIM", "64"))

# ── Behaviour thresholds ──────────────────────────────────────────────────────
PURCHASE_THRESHOLD   = float(os.getenv("PURCHASE_THRESHOLD",   "3.0"))
RECOMMENDATION_LIMIT = int(os.getenv("RECOMMENDATION_LIMIT",   "8"))

# ── HTTP client ───────────────────────────────────────────────────────────────
HTTP_TIMEOUT    = float(os.getenv("HTTP_TIMEOUT",    "8.0"))
HTTP_MAX_RETRY  = int(os.getenv("HTTP_MAX_RETRY",    "3"))

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Ensure artifacts dir exists
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
