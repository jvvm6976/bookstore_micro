"""Ecommerce AI Assistant Service FastAPI entry point."""

import logging
import os

import django
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.logging import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "recommender_ai_service.settings")
django.setup()
logger.info("Django ORM initialized")

from app.api.routes_lazy import get_router

router = get_router()

app = FastAPI(
    title="Ecommerce AI Assistant Service",
    description=(
        "AI-powered assistant for Ecommerce platform.\n\n"
        "RAG-based chatbot, KB management, and recommendation endpoints."
    ),
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
    from app.services.model_scheduler import start_training_scheduler
    from app.services.rag_retrieval import rag_service

    logger.info("Loading KB from disk...")
    count = kb_service.load_from_disk()
    if count == 0:
        logger.info("No KB on disk - will reindex when /api/v1/kb/reindex is called")

    logger.info("Building FAISS index from existing KB...")
    try:
        indexed = rag_service.load_index()
        if not indexed and count > 0:
            rag_service.build_index()
    except Exception as exc:
        logger.warning("FAISS index build skipped: %s", exc)

    start_training_scheduler()

    logger.info("AI Assistant Service ready. KB entries: %d", count)
