"""
Recommendation Engine
──────────────────────
Combines behavior scores + content-based filtering + popularity
to produce ranked book recommendations.

Priority order:
  1. Books in "likely_to_buy" (high behavior score, not yet purchased)
  2. Books matching top categories/authors
  3. Globally popular books (fallback)
"""
import logging
from collections import defaultdict

from ..application.hybrid_recommender import hybrid_recommendation_service
from ..models import Recommendation
from ..clients import book_client, order_client, comment_client
from . import behavior as beh

logger = logging.getLogger(__name__)


def _book_category_key(book: dict) -> str | None:
    category_detail = book.get('category_detail')
    if isinstance(category_detail, dict):
        slug = category_detail.get('slug')
        if slug:
            return str(slug)
        name = category_detail.get('name')
        if name:
            return str(name)

    category = book.get('category')
    if category is None:
        return None
    return str(category)


def _book_title(book: dict) -> str:
    return str(book.get('title') or book.get('name') or '')


def _get_purchased_ids(customer_id: int) -> set[int]:
    orders = order_client.get_orders_by_customer(customer_id)
    ids = set()
    for order in orders:
        for item in order.get('items', []):
            if item.get('book_id'):
                ids.add(item['book_id'])
    return ids


def _global_rating_map() -> dict[int, dict]:
    """Build {book_id: {avg, count}} from comment service."""
    comments = comment_client.get_all_comments()
    stats: dict[int, dict] = defaultdict(lambda: {'sum': 0.0, 'count': 0})
    for c in comments:
        bid = c.get('book_id')
        r   = c.get('rating')
        if bid and r:
            stats[bid]['sum']   += float(r)
            stats[bid]['count'] += 1
    return {
        bid: {
            'avg':   s['sum'] / s['count'],
            'count': s['count'],
        }
        for bid, s in stats.items() if s['count'] > 0
    }


def generate(customer_id: int, limit: int = 8) -> list[dict]:
    """
    Generate recommendations for a customer.
    Returns list of {book_id, score, reason, book_detail}.
    """
    try:
        hybrid_recs = hybrid_recommendation_service.get_personalized(customer_id=customer_id, limit=limit)
    except Exception as exc:
        logger.warning("Hybrid recommender failed, falling back to legacy logic: %s", exc)
        hybrid_recs = []

    if hybrid_recs:
        chosen = []
        for item in hybrid_recs[:limit]:
            book_id = item.get('product_id') or item.get('book_id')
            book = book_client.get_book(book_id) or {}
            if not book:
                continue
            chosen.append({
                'book_id': book_id,
                'score': item.get('score', 0),
                'reason': item.get('reason', 'phổ biến'),
                'book': {**book, 'title': _book_title(book), 'category': _book_category_key(book) or ''},
            })
        if chosen:
            Recommendation.objects.filter(customer_id=customer_id).delete()
            for c in chosen:
                Recommendation.objects.create(
                    customer_id=customer_id,
                    recommended_book_id=c['book_id'],
                    score=c['score'],
                    reason=c['reason'],
                )
            logger.info("Generated %d hybrid recommendations for C%s", len(chosen), customer_id)
            return chosen

    # 1. Build/refresh behavior profile
    profile = beh.build_profile(customer_id)
    purchased = _get_purchased_ids(customer_id)
    behavior_scores = beh.get_book_scores(customer_id)

    # 2. Fetch all books
    all_books = book_client.get_all_books()
    if not all_books:
        logger.warning("No books available from book-service")
        return []

    rating_map = _global_rating_map()

    top_cats    = {x['category'] for x in profile.top_categories}
    top_authors = {x['author']   for x in profile.top_authors}

    candidates = []
    for book in all_books:
        bid = book.get('id')
        if not bid or bid in purchased or book.get('stock', 0) <= 0:
            continue

        book_category = _book_category_key(book)

        score  = 0.0
        reasons = []

        # Behavior score (direct signal)
        bscore = behavior_scores.get(bid, 0)
        if bscore >= 3:
            score += bscore * 0.5
            reasons.append(f"bạn đã xem/tìm {int(bscore)} lần")

        # Category match
        if book_category in top_cats:
            score += 2.0
            reasons.append(f"thể loại {book_category} bạn yêu thích")

        # Author match
        if book.get('author') in top_authors:
            score += 1.5
            reasons.append(f"tác giả {book['author']} bạn quan tâm")

        # Popularity (rating × log(count))
        rm = rating_map.get(bid, {})
        if rm.get('count', 0) > 0:
            import math
            pop = rm['avg'] * math.log1p(rm['count']) * 0.3
            score += pop
            if rm['avg'] >= 4.0:
                reasons.append(f"đánh giá cao ({rm['avg']:.1f}★)")

        if score > 0 or not reasons:
            candidates.append({
                'book_id': bid,
                'score':   round(score, 3),
                'reason':  ', '.join(reasons) if reasons else 'phổ biến',
                'book':    {**book, 'title': _book_title(book), 'category': book_category or ''},
            })

    # Sort and take top N
    candidates.sort(key=lambda x: x['score'], reverse=True)
    chosen = candidates[:limit]

    # Persist to DB
    Recommendation.objects.filter(customer_id=customer_id).delete()
    for c in chosen:
        Recommendation.objects.create(
            customer_id=customer_id,
            recommended_book_id=c['book_id'],
            score=c['score'],
            reason=c['reason'],
        )

    logger.info("Generated %d recommendations for C%s", len(chosen), customer_id)
    return chosen


def get_cached(customer_id: int) -> list[dict]:
    """Return cached recommendations with book detail."""
    recs = Recommendation.objects.filter(customer_id=customer_id).order_by('-score')
    result = []
    for r in recs:
        book = book_client.get_book(r.recommended_book_id) or {}
        result.append({
            'book_id': r.recommended_book_id,
            'score':   r.score,
            'reason':  r.reason,
            'book':    {**book, 'title': _book_title(book), 'category': _book_category_key(book) or ''},
        })
    return result
