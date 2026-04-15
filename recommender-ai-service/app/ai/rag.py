"""
RAG (Retrieval-Augmented Generation) Module
─────────────────────────────────────────────
Lightweight keyword-based retrieval (no external LLM required).
Uses TF-IDF-style scoring over KB entries.

For production: swap _score_entry() with a vector similarity call
(e.g. sentence-transformers + pgvector).
"""
import logging
import re
from collections import Counter
from ..models import KBEntry

logger = logging.getLogger(__name__)

STOPWORDS = {
    'va', 'cua', 'la', 'co', 'cho', 'voi', 'trong', 'toi', 'ban', 'duoc',
    'the', 'a', 'an', 'is', 'are', 'to', 'do', 'how', 'what', 'where',
    'i', 'my', 'me', 'you', 'your', 'it', 'this', 'that',
    'và', 'của', 'là', 'có', 'cho', 'với', 'trong', 'tôi', 'bạn', 'được',
}


def _tokenize(text: str) -> list[str]:
    words = re.findall(r'\b\w+\b', text.lower())
    return [w for w in words if len(w) > 2 and w not in STOPWORDS]


def _score_entry(entry: KBEntry, query_tokens: list[str]) -> float:
    """Score a KB entry against query tokens."""
    score = 0.0
    entry_tokens = _tokenize(entry.title + ' ' + entry.content)
    entry_keywords = [k.lower() for k in (entry.keywords or [])]

    query_counter = Counter(query_tokens)
    for token, freq in query_counter.items():
        # Keyword match (higher weight)
        if token in entry_keywords:
            score += 3.0 * freq
        # Content match
        if token in entry_tokens:
            score += 1.0 * freq
        # Title match (medium weight)
        if token in _tokenize(entry.title):
            score += 2.0 * freq

    return score


def retrieve(query: str, top_k: int = 3, category: str = None) -> list[dict]:
    """
    Retrieve top_k KB entries relevant to the query.
    Returns list of {entry, score, snippet}.
    """
    if not query or not query.strip():
        return []

    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    qs = KBEntry.objects.all()
    if category:
        qs = qs.filter(category=category)

    scored = []
    for entry in qs:
        s = _score_entry(entry, query_tokens)
        if s > 0:
            scored.append((s, entry))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for score, entry in scored[:top_k]:
        # Build a short snippet (first 200 chars)
        snippet = entry.content[:200] + ('...' if len(entry.content) > 200 else '')
        results.append({
            'id':       entry.id,
            'category': entry.category,
            'title':    entry.title,
            'content':  entry.content,
            'snippet':  snippet,
            'score':    round(score, 2),
        })

    logger.debug("RAG retrieved %d entries for query: %s", len(results), query[:50])
    return results


def build_context(query: str, top_k: int = 3) -> str:
    """
    Build a context string from retrieved KB entries.
    Used to augment chatbot responses.
    """
    entries = retrieve(query, top_k=top_k)
    if not entries:
        return ""
    parts = []
    for e in entries:
        parts.append(f"[{e['title']}]: {e['content']}")
    return "\n\n".join(parts)
