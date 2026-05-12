"""
Customer Behavior Analysis Module
──────────────────────────────────
Scores each (customer, book) pair based on interaction history.

Scoring formula:
  score = Σ weight[interaction_type] × count

  view     × 1
  search   × 2
  cart     × 4
  purchase × 8
  rate     × 3

  score >= PURCHASE_THRESHOLD (3) → "likely to buy"

This module:
  1. Ingests raw interaction events (track_interaction)
  2. Builds/refreshes CustomerBehaviorProfile
  3. Returns ranked book candidates for a customer
"""
import logging
from collections import defaultdict

from ..models import (
    CustomerBookInteraction,
    CustomerBehaviorProfile,
    INTERACTION_WEIGHTS,
    PURCHASE_THRESHOLD,
)
from ..clients import book_client

logger = logging.getLogger(__name__)


def track(customer_id: int, book_id: int, interaction_type: str, rating: int = None) -> dict:
    """
    Record or increment an interaction.
    Returns the updated interaction record as dict.
    """
    if interaction_type not in INTERACTION_WEIGHTS:
        interaction_type = 'view'

    obj, created = CustomerBookInteraction.objects.get_or_create(
        customer_id=customer_id,
        book_id=book_id,
        interaction_type=interaction_type,
        defaults={'count': 1, 'rating': rating},
    )
    if not created:
        obj.count += 1
        if rating is not None:
            obj.rating = rating
        obj.save(update_fields=['count', 'rating', 'timestamp'])

    logger.debug("Tracked %s C%s→B%s (count=%s)", interaction_type, customer_id, book_id, obj.count)
    return {
        'customer_id':       customer_id,
        'book_id':           book_id,
        'interaction_type':  interaction_type,
        'count':             obj.count,
        'weighted_score':    obj.weighted_score,
        'created':           created,
    }


def get_book_scores(customer_id: int) -> dict[int, float]:
    """
    Return {book_id: total_score} for a customer.
    """
    interactions = CustomerBookInteraction.objects.filter(customer_id=customer_id)
    scores: dict[int, float] = defaultdict(float)
    for ix in interactions:
        scores[ix.book_id] += ix.weighted_score
    return dict(scores)


def get_likely_to_buy(customer_id: int) -> list[int]:
    """
    Return book_ids where score >= PURCHASE_THRESHOLD.
    Sorted by score descending.
    """
    scores = get_book_scores(customer_id)
    likely = [(bid, s) for bid, s in scores.items() if s >= PURCHASE_THRESHOLD]
    likely.sort(key=lambda x: x[1], reverse=True)
    return [bid for bid, _ in likely]


def build_profile(customer_id: int) -> CustomerBehaviorProfile:
    """
    Build/refresh the aggregated behavior profile for a customer.
    Fetches book metadata to compute category/author affinity.
    """
    scores = get_book_scores(customer_id)
    likely = get_likely_to_buy(customer_id)

    # Fetch book metadata for scored books
    category_scores: dict[str, float] = defaultdict(float)
    author_scores:   dict[str, float] = defaultdict(float)

    for book_id, score in scores.items():
        book = book_client.get_book(book_id)
        if not book:
            continue
        cat = book.get('category')
        author = book.get('author')
        if cat:
            category_scores[cat] += score
        if author:
            author_scores[author] += score

    top_categories = sorted(
        [{'category': c, 'score': s} for c, s in category_scores.items()],
        key=lambda x: x['score'], reverse=True
    )[:5]
    top_authors = sorted(
        [{'author': a, 'score': s} for a, s in author_scores.items()],
        key=lambda x: x['score'], reverse=True
    )[:5]

    profile, _ = CustomerBehaviorProfile.objects.update_or_create(
        customer_id=customer_id,
        defaults={
            'top_categories': top_categories,
            'top_authors':    top_authors,
            'total_score':    sum(scores.values()),
            'likely_to_buy':  likely[:20],
        },
    )
    logger.info("Built profile for C%s: cats=%s, likely=%s books",
                customer_id, len(top_categories), len(likely))
    return profile


def get_profile(customer_id: int) -> CustomerBehaviorProfile | None:
    try:
        return CustomerBehaviorProfile.objects.get(customer_id=customer_id)
    except CustomerBehaviorProfile.DoesNotExist:
        return None


def get_popular_books(limit: int = 10) -> list[dict]:
    """
    Global popularity: books with highest total interaction score across all customers.
    Returns [{book_id, total_score, interaction_count}]
    """
    from django.db.models import Sum, Count
    qs = (
        CustomerBookInteraction.objects
        .values('book_id')
        .annotate(
            total_count=Sum('count'),
            interaction_count=Count('id'),
        )
        .order_by('-total_count')[:limit]
    )
    result = []
    for row in qs:
        # compute weighted score
        interactions = CustomerBookInteraction.objects.filter(book_id=row['book_id'])
        wscore = sum(i.weighted_score for i in interactions)
        result.append({
            'book_id':           row['book_id'],
            'total_score':       wscore,
            'interaction_count': row['interaction_count'],
        })
    result.sort(key=lambda x: x['total_score'], reverse=True)
    return result
