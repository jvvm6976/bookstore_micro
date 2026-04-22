"""Central configuration via environment variables."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ── Service URLs ──────────────────────────────────────────────────────────────
PRODUCT_SERVICE_URL  = os.getenv(
    "PRODUCT_SERVICE_URL",
    os.getenv("BOOK_SERVICE_URL", os.getenv("CATALOG_SERVICE_URL", "http://product-service:8000")),
)
# Backward compatibility for old imports/env names.
BOOK_SERVICE_URL     = PRODUCT_SERVICE_URL
CATALOG_SERVICE_URL  = PRODUCT_SERVICE_URL
CUSTOMER_SERVICE_URL = os.getenv("CUSTOMER_SERVICE_URL", "http://customer-service:8000")
ORDER_SERVICE_URL    = os.getenv("ORDER_SERVICE_URL",    "http://order-service:8000")
COMMENT_SERVICE_URL  = os.getenv("COMMENT_SERVICE_URL",  "http://comment-rate-service:8000")
SHIP_SERVICE_URL     = os.getenv("SHIP_SERVICE_URL",     "http://ship-service:8000")
PAY_SERVICE_URL      = os.getenv("PAY_SERVICE_URL",      "http://pay-service:8000")

# ── DB ────────────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:root@db-postgres:5432/ecommerce_recommender",
)

# ── AI / Model ────────────────────────────────────────────────────────────────
ARTIFACTS_DIR    = Path(os.getenv("ARTIFACTS_DIR", str(BASE_DIR / "artifacts")))
FAISS_INDEX_PATH = ARTIFACTS_DIR / "kb_faiss.index"
FAISS_META_PATH  = ARTIFACTS_DIR / "kb_meta.json"
TRAIN_DATA_PATH  = Path(os.getenv("TRAIN_DATA_PATH", str(BASE_DIR / "data" / "data_user5000.csv")))

# Behavior model path is kept for backward compatibility with existing imports.
MODEL_PATH = Path(os.getenv("BEHAVIOR_MODEL_PATH", str(ARTIFACTS_DIR / "behavior_model.pt")))

# Sequence LSTM path (Assignment 2a output).
LSTM_MODEL_PATH = Path(
    os.getenv(
        "LSTM_MODEL_PATH",
        str(BASE_DIR / "artifacts" / "2a" / "lstm_next_action.pt"),
    )
)

EMBED_DIM = int(os.getenv("EMBED_DIM", "64"))
GRAPH_BOOTSTRAP_FROM_TRAIN = os.getenv("GRAPH_BOOTSTRAP_FROM_TRAIN", "1") == "1"

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
