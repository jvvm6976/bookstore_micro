"""
KBIngestionService
───────────────────
Builds and maintains the Knowledge Base from:
  1. Seed data (FAQ, policies) — loaded from data/seed_kb.json
  2. Product catalog (from product-service — đa domain)
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

KB_JSON_PATH   = ARTIFACTS_DIR / "kb_entries.json"
SEED_DATA_PATH = BASE_DIR / "data" / "seed_kb.json"

_kb_entries: list[dict[str, Any]] = []


def _ensure_loaded_from_disk() -> None:
    global _kb_entries
    if _kb_entries or not KB_JSON_PATH.exists():
        return
    try:
        with open(KB_JSON_PATH, encoding="utf-8") as f:
            _kb_entries = json.load(f)
        logger.info("Lazy-loaded %d KB entries from disk", len(_kb_entries))
    except Exception as exc:
        logger.warning("Could not lazy-load KB entries: %s", exc)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _chunk_text(text: str, max_chars: int = 400) -> list[str]:
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
    return {
        "id":       entry_id,
        "category": category,
        "title":    title,
        "content":  _normalize(content),
        "keywords": [k.lower() for k in keywords if k],
        "metadata": metadata or {},
    }


def _load_seed() -> list[dict]:
    if SEED_DATA_PATH.exists():
        with open(SEED_DATA_PATH, encoding="utf-8") as f:
            return json.load(f)
    logger.warning("Seed KB file not found at %s", SEED_DATA_PATH)
    return []


def _ingest_products(products: list[dict]) -> list[dict]:
    """Ingest products from product-service (multi-domain)."""
    entries = []
    for p in products:
        pid   = p.get("id")
        name  = p.get("name") or p.get("title") or f"Product {pid}"
        cat   = p.get("category") or p.get("category_slug") or ""
        ptype = p.get("product_type") or ""
        brand = p.get("brand") or p.get("attributes", {}).get("brand") or ""
        desc  = p.get("description", "")
        price = float(p.get("price") or 0)
        stock = p.get("stock", 0)
        attrs = p.get("attributes") or {}

        # Build rich content string
        content_parts = [f"Sản phẩm '{name}'"]
        if brand:
            content_parts.append(f"thương hiệu {brand}")
        if cat:
            content_parts.append(f"danh mục: {cat}")
        if ptype:
            content_parts.append(f"loại: {ptype}")
        content_parts.append(f"Giá: {int(price):,}đ.")
        if desc:
            content_parts.append(f"Mô tả: {desc}")
        content_parts.append(f"Còn {stock} sản phẩm trong kho.")

        # Add key attributes
        for k, v in list(attrs.items())[:5]:
            if v and k not in ("isbn",):
                content_parts.append(f"{k}: {v}.")

        content = " ".join(content_parts)

        keywords = [
            name.lower(), cat, ptype, brand.lower(),
            "san pham", "product", str(pid),
        ]
        # Add author for books
        if attrs.get("author"):
            keywords.append(attrs["author"].lower())

        for i, chunk in enumerate(_chunk_text(content)):
            entries.append(_make_entry(
                entry_id=f"product_{pid}_chunk{i}",
                category="product",
                title=name,
                content=chunk,
                keywords=keywords,
                metadata={
                    "product_id":   pid,
                    "price":        price,
                    "category":     cat,
                    "product_type": ptype,
                    "brand":        brand,
                    "source_type":  "product",
                },
            ))
    return entries


def _ingest_reviews(comments: list[dict], products: list[dict]) -> list[dict]:
    product_map = {p["id"]: p.get("name") or p.get("title") or f"Product {p['id']}"
                   for p in products if p.get("id")}
    entries = []
    from collections import defaultdict
    by_product: dict[int, list] = defaultdict(list)
    for c in comments:
        pid = c.get("product_id") or c.get("book_id")
        if pid:
            by_product[pid].append(c)

    for pid, reviews in by_product.items():
        if not reviews:
            continue
        name = product_map.get(pid, f"Product {pid}")
        avg  = sum(r.get("rating", 0) for r in reviews) / len(reviews)
        top  = sorted(reviews, key=lambda r: r.get("rating", 0), reverse=True)[:3]
        snippets = ". ".join(r.get("content", "")[:100] for r in top if r.get("content"))
        content = (
            f"Đánh giá sản phẩm '{name}': {len(reviews)} đánh giá, "
            f"điểm trung bình {avg:.1f}/5. "
            + (f"Nhận xét tiêu biểu: {snippets}" if snippets else "")
        )
        entries.append(_make_entry(
            entry_id=f"review_{pid}",
            category="review",
            title=f"Đánh giá: {name}",
            content=content,
            keywords=[name.lower(), "review", "danh gia", "rating", str(pid)],
            metadata={"product_id": pid, "avg_rating": round(avg, 2),
                      "review_count": len(reviews), "source_type": "review"},
        ))
    return entries


def get_all_entries() -> list[dict]:
    _ensure_loaded_from_disk()
    return list(_kb_entries)


def get_stats() -> dict:
    _ensure_loaded_from_disk()
    from collections import Counter
    cats = Counter(e["category"] for e in _kb_entries)
    return {
        "total_entries": len(_kb_entries),
        "by_category":   dict(cats),
    }


def reindex() -> int:
    """Full reindex: seed + products (multi-domain) + reviews."""
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
                metadata={**item.get("metadata", {}), "source_type": item.get("category", "faq")},
            ))

    # 2. Products from product-service (multi-domain)
    products = catalog_client.get_all_products(limit=500)
    entries.extend(_ingest_products(products))

    # 3. Reviews
    comments = comment_client.get_all_comments()
    entries.extend(_ingest_reviews(comments, products))

    _kb_entries = entries

    KB_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(KB_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    logger.info("KB reindexed: %d entries (products=%d, reviews=%d, seed=%d)",
                len(entries), len(products), len(comments), len(seed))
    return len(entries)


def load_from_disk() -> int:
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
