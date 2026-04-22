"""
KBIngestionService
───────────────────
Builds and maintains the Knowledge Base from:
  1. Seed data (FAQ, policies) — loaded from data/seed_kb.json
  2. Book catalog (from book-service)
  3. Reviews (from comment-rate-service)

Each KB entry is chunked and stored in memory + persisted to JSON.
The FAISS index is built by RAGRetrievalService after ingestion.
"""
from __future__ import annotations
import json
import logging
import re
from pathlib import Path
from typing import Any

from ..core.config import ARTIFACTS_DIR, BASE_DIR
from ..clients.catalog_client import catalog_client
from ..clients.comment_client import comment_client

logger = logging.getLogger(__name__)

KB_JSON_PATH = ARTIFACTS_DIR / "kb_entries.json"
SEED_DATA_PATH = BASE_DIR / "data" / "seed_kb.json"

# In-memory store
_kb_entries: list[dict[str, Any]] = []


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _chunk_text(text: str, max_chars: int = 400) -> list[str]:
    """Split long text into overlapping chunks."""
    if len(text) <= max_chars:
        return [text]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks, current = [], ""
    for sent in sentences:
        if len(current) + len(sent) + 1 <= max_chars:
            current = (current + " " + sent).strip()
        else:
            if current:
                chunks.append(current)
            current = sent
    if current:
        chunks.append(current)
    return chunks or [text[:max_chars]]


def _make_entry(
    entry_id: str,
    category: str,
    title: str,
    content: str,
    keywords: list[str],
    metadata: dict | None = None,
) -> dict[str, Any]:
    normalized_keywords: list[str] = []
    for k in keywords:
        if k is None:
            continue
        normalized_keywords.append(str(k).lower())

    return {
        "id":       entry_id,
        "category": category,
        "title":    title,
        "content":  _normalize(content),
        "keywords": normalized_keywords,
        "metadata": metadata or {},
    }


# ── Seed data ─────────────────────────────────────────────────────────────────

def _load_seed() -> list[dict]:
    if SEED_DATA_PATH.exists():
        with open(SEED_DATA_PATH, encoding="utf-8") as f:
            return json.load(f)
    logger.warning("Seed KB file not found at %s", SEED_DATA_PATH)
    return []


# ── Ingest from services ──────────────────────────────────────────────────────

def _ingest_books(books: list[dict]) -> list[dict]:
    entries = []
    for book in books:
        bid   = book.get("id")
        title = book.get("title", f"Book {bid}")
        author = book.get("author", "")
        cat    = book.get("category", "")
        desc   = book.get("description", "")
        price  = book.get("price", 0)
        stock  = book.get("stock", 0)

        content = (
            f"Sách '{title}'"
            + (f" của tác giả {author}" if author else "")
            + f". Thể loại: {cat}. Giá: {int(float(price)):,}đ."
            + (f" Mô tả: {desc}" if desc else "")
            + f" Còn {stock} cuốn trong kho."
        )
        keywords = [
            title.lower(),
            author.lower() if author else "",
            cat,
            "sach", "book",
            str(bid),
        ]
        keywords = [k for k in keywords if k]

        for i, chunk in enumerate(_chunk_text(content)):
            entries.append(_make_entry(
                entry_id=f"book_{bid}_chunk{i}",
                category="book",
                title=title,
                content=chunk,
                keywords=keywords,
                metadata={"book_id": bid, "price": float(price), "category": cat, "author": author},
            ))
    return entries


def _ingest_reviews(comments: list[dict], books: list[dict]) -> list[dict]:
    book_map = {b["id"]: b.get("title", f"Book {b['id']}") for b in books if b.get("id")}
    entries = []
    # Group by book
    from collections import defaultdict
    by_book: dict[int, list] = defaultdict(list)
    for c in comments:
        bid = c.get("book_id")
        if bid:
            by_book[bid].append(c)

    for bid, reviews in by_book.items():
        if not reviews:
            continue
        title = book_map.get(bid, f"Book {bid}")
        avg   = sum(r.get("rating", 0) for r in reviews) / len(reviews)
        top_reviews = sorted(reviews, key=lambda r: r.get("rating", 0), reverse=True)[:3]
        snippets = ". ".join(r.get("content", "")[:100] for r in top_reviews if r.get("content"))
        content = (
            f"Đánh giá sách '{title}': {len(reviews)} đánh giá, "
            f"điểm trung bình {avg:.1f}/5. "
            + (f"Nhận xét tiêu biểu: {snippets}" if snippets else "")
        )
        entries.append(_make_entry(
            entry_id=f"review_{bid}",
            category="review",
            title=f"Đánh giá: {title}",
            content=content,
            keywords=[title.lower(), "review", "danh gia", "rating", str(bid)],
            metadata={"book_id": bid, "avg_rating": round(avg, 2), "review_count": len(reviews)},
        ))
    return entries


# ── Public API ────────────────────────────────────────────────────────────────

def get_all_entries() -> list[dict]:
    return list(_kb_entries)


def get_stats() -> dict:
    from collections import Counter
    cats = Counter(e["category"] for e in _kb_entries)
    return {
        "total_entries": len(_kb_entries),
        "by_category":   dict(cats),
    }


def reindex() -> int:
    """Full reindex: seed + books + reviews."""
    global _kb_entries
    entries: list[dict] = []

    # 1. Seed FAQ/policy
    seed = _load_seed()
    for i, item in enumerate(seed):
        for j, chunk in enumerate(_chunk_text(item.get("content", ""))):
            entries.append(_make_entry(
                entry_id=f"seed_{i}_chunk{j}",
                category=item.get("category", "faq"),
                title=item.get("title", ""),
                content=chunk,
                keywords=item.get("keywords", []),
                metadata=item.get("metadata", {}),
            ))

    # 2. Books
    books = catalog_client.get_all_products(limit=500)
    entries.extend(_ingest_books(books))

    # 3. Reviews
    comments = comment_client.get_all_comments()
    entries.extend(_ingest_reviews(comments, books))

    _kb_entries = entries

    # Persist
    KB_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(KB_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    logger.info("KB reindexed: %d entries", len(entries))
    return len(entries)


def load_from_disk() -> int:
    """Load previously persisted KB from disk."""
    global _kb_entries
    if KB_JSON_PATH.exists():
        with open(KB_JSON_PATH, encoding="utf-8") as f:
            _kb_entries = json.load(f)
        logger.info("Loaded %d KB entries from disk", len(_kb_entries))
        return len(_kb_entries)
    logger.info("No KB on disk, running initial reindex...")
    return reindex()


kb_service = type("KBService", (), {
    "reindex":         staticmethod(reindex),
    "load_from_disk":  staticmethod(load_from_disk),
    "get_all_entries": staticmethod(get_all_entries),
    "get_stats":       staticmethod(get_stats),
})()
