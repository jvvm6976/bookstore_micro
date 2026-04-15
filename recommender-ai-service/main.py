"""
MoonBooks AI Assistant Service
FastAPI application entry point.
"""
import logging
import os

import django
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.logging import setup_logging
from app.api.routes import router

# ── Setup ─────────────────────────────────────────────────────────────────────
setup_logging()
logger = logging.getLogger(__name__)

# Bootstrap Django ORM (for interaction tracking / session storage)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "recommender_ai_service.settings")
try:
    django.setup()
    logger.info("Django ORM initialized")
except Exception as exc:
    logger.warning("Django setup failed (non-fatal): %s", exc)

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="MoonBooks AI Assistant Service",
    description=(
        "AI-powered assistant for MoonBooks e-commerce platform.\n\n"
        "Features: personalized recommendations, behavior analysis, "
        "RAG-based chatbot, KB management, order support."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.on_event("startup")
async def startup():
    """Initialize KB and FAISS index on startup."""
    from app.services.kb_ingestion import kb_service
    from app.services.rag_retrieval import rag_service

    logger.info("Loading KB from disk...")
    count = kb_service.load_from_disk()
    if count == 0:
        logger.info("No KB on disk — will reindex when /api/v1/kb/reindex is called")

    logger.info("Building FAISS index from existing KB...")
    try:
        indexed = rag_service.load_index()
        if not indexed and count > 0:
            rag_service.build_index()
    except Exception as exc:
        logger.warning("FAISS index build skipped: %s", exc)

    logger.info("AI Assistant Service ready. KB entries: %d", count)
