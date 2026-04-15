"""
RAGRetrievalService
────────────────────
Local retrieval pipeline using FAISS + TF-IDF-style embeddings.
No external LLM required.

Pipeline:
  1. Build TF-IDF sparse vectors from KB entries
  2. Store in FAISS flat index (L2)
  3. At query time: vectorize query → FAISS search → return top-k entries
  4. Keyword fallback if FAISS returns low-confidence results
"""
from __future__ import annotations
import json
import logging
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from ..core.config import FAISS_INDEX_PATH, FAISS_META_PATH, EMBED_DIM
from .kb_ingestion import get_all_entries

logger = logging.getLogger(__name__)

# ── Vocabulary & TF-IDF ───────────────────────────────────────────────────────

_vocab:      dict[str, int] = {}
_idf:        dict[str, float] = {}
_index       = None   # faiss.IndexFlatL2
_index_meta: list[dict] = []   # parallel list of entry metadata

STOPWORDS = {
    "va", "cua", "la", "co", "cho", "voi", "trong", "toi", "ban", "duoc",
    "the", "a", "an", "is", "are", "to", "do", "how", "what", "where",
    "i", "my", "me", "you", "your", "it", "this", "that", "of", "in",
    "và", "của", "là", "có", "cho", "với", "trong", "tôi", "bạn", "được",
}


def _tokenize(text: str) -> list[str]:
    words = re.findall(r"\b\w+\b", text.lower())
    return [w for w in words if len(w) > 2 and w not in STOPWORDS]


def _build_vocab(entries: list[dict]) -> dict[str, int]:
    all_tokens: list[str] = []
    for e in entries:
        all_tokens.extend(_tokenize(e["title"] + " " + e["content"]))
        all_tokens.extend(e.get("keywords", []))
    freq = Counter(all_tokens)
    # Keep top EMBED_DIM * 10 tokens by frequency
    top = [w for w, _ in freq.most_common(EMBED_DIM * 10)]
    return {w: i for i, w in enumerate(top)}


def _compute_idf(entries: list[dict], vocab: dict[str, int]) -> dict[str, float]:
    N = len(entries)
    df: dict[str, int] = Counter()
    for e in entries:
        tokens = set(_tokenize(e["title"] + " " + e["content"]))
        tokens.update(e.get("keywords", []))
        for t in tokens:
            if t in vocab:
                df[t] += 1
    return {w: math.log((N + 1) / (df.get(w, 0) + 1)) for w in vocab}


def _vectorize(text: str, keywords: list[str] | None = None) -> np.ndarray:
    """Convert text to a fixed-dim TF-IDF vector."""
    tokens = _tokenize(text)
    if keywords:
        tokens.extend([k.lower() for k in keywords])
    tf = Counter(tokens)
    vec = np.zeros(EMBED_DIM, dtype=np.float32)
    for token, count in tf.items():
        idx = _vocab.get(token)
        if idx is not None and idx < EMBED_DIM:
            idf_val = _idf.get(token, 1.0)
            vec[idx] += (count / max(len(tokens), 1)) * idf_val
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm
    return vec


# ── FAISS index ───────────────────────────────────────────────────────────────

def build_index(entries: list[dict] | None = None) -> int:
    """Build FAISS index from KB entries. Returns number of indexed entries."""
    global _vocab, _idf, _index, _index_meta

    try:
        import faiss
    except ImportError:
        logger.warning("faiss-cpu not installed — RAG will use keyword-only fallback")
        return 0

    if entries is None:
        entries = get_all_entries()
    if not entries:
        logger.warning("No KB entries to index")
        return 0

    _vocab = _build_vocab(entries)
    _idf   = _compute_idf(entries, _vocab)

    vectors = np.stack([
        _vectorize(e["title"] + " " + e["content"], e.get("keywords"))
        for e in entries
    ]).astype(np.float32)

    _index = faiss.IndexFlatIP(EMBED_DIM)   # Inner product (cosine after normalization)
    _index.add(vectors)
    _index_meta = entries

    # Persist
    FAISS_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(_index, str(FAISS_INDEX_PATH))
    with open(FAISS_META_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False)

    logger.info("FAISS index built: %d vectors (dim=%d)", len(entries), EMBED_DIM)
    return len(entries)


def load_index() -> bool:
    """Load persisted FAISS index from disk."""
    global _vocab, _idf, _index, _index_meta
    try:
        import faiss
    except ImportError:
        return False

    if not FAISS_INDEX_PATH.exists() or not FAISS_META_PATH.exists():
        return False
    try:
        _index = faiss.read_index(str(FAISS_INDEX_PATH))
        with open(FAISS_META_PATH, encoding="utf-8") as f:
            _index_meta = json.load(f)
        # Rebuild vocab/idf from meta
        _vocab = _build_vocab(_index_meta)
        _idf   = _compute_idf(_index_meta, _vocab)
        logger.info("Loaded FAISS index: %d entries", len(_index_meta))
        return True
    except Exception as exc:
        logger.error("Failed to load FAISS index: %s", exc)
        return False


# ── Keyword fallback ──────────────────────────────────────────────────────────

def _keyword_score(entry: dict, query_tokens: list[str]) -> float:
    score = 0.0
    entry_tokens = set(_tokenize(entry["title"] + " " + entry["content"]))
    entry_kw     = set(k.lower() for k in entry.get("keywords", []))
    for t in query_tokens:
        if t in entry_kw:
            score += 3.0
        elif t in entry_tokens:
            score += 1.0
        if t in _tokenize(entry["title"]):
            score += 2.0
    return score


def _keyword_retrieve(query: str, top_k: int, category: str | None) -> list[dict]:
    entries = get_all_entries()
    if category:
        entries = [e for e in entries if e.get("category") == category]
    tokens = _tokenize(query)
    scored = [(e, _keyword_score(e, tokens)) for e in entries]
    scored = [(e, s) for e, s in scored if s > 0]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [
        {**e, "retrieval_score": round(s, 3), "retrieval_method": "keyword"}
        for e, s in scored[:top_k]
    ]


# ── Main retrieve ─────────────────────────────────────────────────────────────

def retrieve(
    query: str,
    top_k: int = 3,
    category: str | None = None,
    min_score: float = 0.05,
) -> list[dict]:
    """
    Retrieve top_k KB entries for a query.
    Returns list of entry dicts with added 'retrieval_score' and 'retrieval_method'.
    """
    if not query.strip():
        return []

    results: list[dict] = []

    # Try FAISS first
    if _index is not None and _index_meta:
        try:
            import faiss as _faiss
            vec = _vectorize(query).reshape(1, -1)
            scores, indices = _index.search(vec, min(top_k * 3, len(_index_meta)))
            for score, idx in zip(scores[0], indices[0]):
                if idx < 0 or float(score) < min_score:
                    continue
                entry = _index_meta[idx]
                if category and entry.get("category") != category:
                    continue
                results.append({
                    **entry,
                    "retrieval_score":  round(float(score), 3),
                    "retrieval_method": "faiss",
                })
                if len(results) >= top_k:
                    break
        except Exception as exc:
            logger.warning("FAISS search failed: %s — falling back to keyword", exc)

    # Keyword fallback / supplement
    if len(results) < top_k:
        kw_results = _keyword_retrieve(query, top_k - len(results), category)
        existing_ids = {r["id"] for r in results}
        for r in kw_results:
            if r["id"] not in existing_ids:
                results.append(r)

    logger.debug("RAG retrieved %d entries for: %s", len(results), query[:60])
    return results[:top_k]


def build_context_string(entries: list[dict]) -> str:
    """Format retrieved entries into a context string for response composition."""
    if not entries:
        return ""
    parts = []
    for e in entries:
        parts.append(f"[{e['title']}]\n{e['content']}")
    return "\n\n---\n\n".join(parts)


rag_service = type("RAGService", (), {
    "retrieve":             staticmethod(retrieve),
    "build_index":          staticmethod(build_index),
    "load_index":           staticmethod(load_index),
    "build_context_string": staticmethod(build_context_string),
})()
