import requests
from collections import Counter, defaultdict

from django.db import models
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import CustomerBookInteraction, Recommendation
from .serializers import CustomerBookInteractionSerializer, RecommendationSerializer


def _extract_results(data):
    if isinstance(data, dict) and isinstance(data.get("results"), list):
        return data["results"]
    if isinstance(data, list):
        return data
    return []


def _safe_get_json(url, *, params=None, timeout=10):
    try:
        resp = requests.get(url, params=params, timeout=timeout)
        if resp.status_code >= 300:
            return None
        return resp.json()
    except requests.exceptions.RequestException:
        return None


class RecommenderViewSet(viewsets.ViewSet):
    """
    Recommendation service.

    This is a pragmatic hybrid recommender for development:
    - Content-based: category/author affinity from purchases & ratings
    - Popularity-based: average rating + review volume
    - Collaborative-lite: uses any stored interactions (if present)
    """

    def list(self, request):
        customer_id = request.query_params.get("customer_id")
        if customer_id:
            return self.get_recommendations(request)
        return Response(
            {
                "message": "Provide customer_id to get personalized recommendations.",
                "example": "/api/recommendations/?customer_id=1&limit=5",
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"])
    def get_recommendations(self, request):
        customer_id = request.query_params.get("customer_id")
        limit = int(request.query_params.get("limit", 5))

        if not customer_id:
            return Response(
                {"error": "customer_id parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cached = Recommendation.objects.filter(customer_id=customer_id).order_by("-score")[:limit]
        if cached.exists():
            return Response(
                {
                    "customer_id": customer_id,
                    "recommendations": RecommendationSerializer(cached, many=True).data,
                    "source": "cache",
                },
                status=status.HTTP_200_OK,
            )

        return self._generate_recommendations(customer_id, limit)

    @action(detail=False, methods=["post"])
    def track_interaction(self, request):
        """
        Track user behavior for better recommendations.

        POST body:
        - customer_id (int)
        - book_id (int)
        - interaction_type (view|cart|purchase|rate)
        - rating (int 1-5, optional)
        """
        serializer = CustomerBookInteractionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        customer_id = serializer.validated_data["customer_id"]
        book_id = serializer.validated_data["book_id"]
        interaction_type = serializer.validated_data["interaction_type"]
        rating = serializer.validated_data.get("rating")

        obj, created = CustomerBookInteraction.objects.get_or_create(
            customer_id=customer_id,
            book_id=book_id,
            interaction_type=interaction_type,
            defaults={"rating": rating},
        )
        if not created and rating is not None:
            obj.rating = rating
            obj.save(update_fields=["rating"])

        return Response(
            {
                "message": "interaction tracked",
                "created": created,
                "interaction": CustomerBookInteractionSerializer(obj).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"])
    def click_recommendation(self, request):
        recommendation_id = request.data.get("recommendation_id")
        if not recommendation_id:
            return Response(
                {"error": "recommendation_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            rec = Recommendation.objects.get(id=recommendation_id)
        except Recommendation.DoesNotExist:
            return Response({"error": "Recommendation not found"}, status=status.HTTP_404_NOT_FOUND)

        rec.clicked = True
        rec.save(update_fields=["clicked"])
        return Response(
            {"message": "click tracked", "recommendation": RecommendationSerializer(rec).data},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"])
    def similar_books(self, request):
        book_id = request.query_params.get("book_id")
        limit = int(request.query_params.get("limit", 5))
        if not book_id:
            return Response({"error": "book_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Use stored interactions (if present) as a collaborative hint.
        fans = CustomerBookInteraction.objects.filter(
            book_id=book_id, interaction_type__in=["rate", "purchase"], rating__gte=4
        ).values_list("customer_id", flat=True)

        similar = (
            CustomerBookInteraction.objects.filter(customer_id__in=fans, rating__gte=4)
            .exclude(book_id=book_id)
            .values("book_id")
            .annotate(score=models.Count("customer_id"))
            .order_by("-score")[:limit]
        )

        return Response(
            {"book_id": book_id, "similar_books": [i["book_id"] for i in similar]},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"])
    def trending_books(self, request):
        limit = int(request.query_params.get("limit", 10))

        comments = _safe_get_json("http://comment-rate-service:8000/api/comments/")
        comments = _extract_results(comments) if comments is not None else []

        stats = defaultdict(lambda: {"count": 0, "sum": 0.0})
        for c in comments if isinstance(comments, list) else []:
            book_id = c.get("book_id")
            rating = c.get("rating")
            if not book_id or rating is None:
                continue
            stats[book_id]["count"] += 1
            stats[book_id]["sum"] += float(rating)

        # Fetch books and attach popularity score.
        books = _safe_get_json("http://book-service:8000/api/books/")
        books = _extract_results(books) if books is not None else []

        def popularity(book):
            s = stats.get(book.get("id"), {"count": 0, "sum": 0.0})
            avg = (s["sum"] / s["count"]) if s["count"] else 0.0
            return (avg, s["count"])

        ranked = sorted(books, key=popularity, reverse=True)[:limit]
        for b in ranked:
            s = stats.get(b.get("id"), {"count": 0, "sum": 0.0})
            b["average_rating"] = (s["sum"] / s["count"]) if s["count"] else 0.0
            b["total_reviews"] = s["count"]

        return Response({"trending": ranked}, status=status.HTTP_200_OK)

    def _generate_recommendations(self, customer_id, limit):
        # Fetch all books once (avoid N requests).
        books_payload = _safe_get_json("http://book-service:8000/api/books/")
        books = _extract_results(books_payload) if books_payload is not None else []
        if not books:
            return Response(
                {"customer_id": customer_id, "recommendations": [], "source": "generated"},
                status=status.HTTP_200_OK,
            )

        book_by_id = {b.get("id"): b for b in books if isinstance(b, dict) and b.get("id") is not None}

        # Purchased books from order-service (best signal).
        orders_payload = _safe_get_json(
            "http://order-service:8000/api/orders/by_customer/", params={"customer_id": customer_id}
        )
        orders = []
        if isinstance(orders_payload, dict) and isinstance(orders_payload.get("orders"), list):
            orders = orders_payload["orders"]
        elif isinstance(orders_payload, list):
            orders = orders_payload

        purchased_book_ids = []
        for order in orders if isinstance(orders, list) else []:
            for item in order.get("items", []) if isinstance(order, dict) else []:
                book_id = item.get("book_id")
                if book_id is not None:
                    purchased_book_ids.append(book_id)

        purchased_set = set(purchased_book_ids)

        # Ratings from comment service (secondary signal).
        comments_payload = _safe_get_json(
            "http://comment-rate-service:8000/api/comments/by_customer/",
            params={"customer_id": customer_id},
        )
        comments = []
        if isinstance(comments_payload, dict) and isinstance(comments_payload.get("comments"), list):
            comments = comments_payload["comments"]
        elif isinstance(comments_payload, list):
            comments = comments_payload

        rated_high = set()
        for c in comments if isinstance(comments, list) else []:
            if c.get("rating", 0) >= 4 and c.get("book_id") is not None:
                rated_high.add(c.get("book_id"))

        # Build affinity profile.
        category_counts = Counter()
        author_counts = Counter()
        for book_id in purchased_book_ids:
            b = book_by_id.get(book_id)
            if not b:
                continue
            if b.get("category"):
                category_counts[b["category"]] += 2
            if b.get("author"):
                author_counts[b["author"]] += 1

        for book_id in rated_high:
            b = book_by_id.get(book_id)
            if not b:
                continue
            if b.get("category"):
                category_counts[b["category"]] += 3
            if b.get("author"):
                author_counts[b["author"]] += 2

        top_categories = {c for c, _ in category_counts.most_common(3)}
        top_authors = {a for a, _ in author_counts.most_common(3)}

        # Global popularity stats.
        all_comments_payload = _safe_get_json("http://comment-rate-service:8000/api/comments/")
        all_comments = _extract_results(all_comments_payload) if all_comments_payload is not None else []
        pop = defaultdict(lambda: {"count": 0, "sum": 0.0})
        for c in all_comments if isinstance(all_comments, list) else []:
            book_id = c.get("book_id")
            rating = c.get("rating")
            if book_id is None or rating is None:
                continue
            pop[book_id]["count"] += 1
            pop[book_id]["sum"] += float(rating)

        def popularity_score(book_id):
            s = pop.get(book_id, {"count": 0, "sum": 0.0})
            avg = (s["sum"] / s["count"]) if s["count"] else 0.0
            volume = min(s["count"], 50) / 50.0
            return (avg / 5.0) * 0.5 + volume * 0.3

        candidates = []
        for b in books:
            if not isinstance(b, dict):
                continue
            book_id = b.get("id")
            if book_id is None or book_id in purchased_set:
                continue
            if b.get("stock", 0) <= 0:
                continue

            score = 0.0
            reason_parts = []

            if top_categories and b.get("category") in top_categories:
                score += 1.0
                reason_parts.append("category match")
            if top_authors and b.get("author") in top_authors:
                score += 0.7
                reason_parts.append("author match")

            score += popularity_score(book_id)
            if pop.get(book_id, {}).get("count", 0) > 0:
                reason_parts.append("popular")

            candidates.append((score, book_id, ", ".join(reason_parts) or "popular"))

        candidates.sort(key=lambda x: x[0], reverse=True)
        chosen = candidates[:limit]

        Recommendation.objects.filter(customer_id=customer_id).delete()
        recs = []
        for score, book_id, reason in chosen:
            recs.append(
                Recommendation.objects.create(
                    customer_id=customer_id,
                    recommended_book_id=book_id,
                    score=float(score),
                    reason=reason,
                )
            )

        # Include book detail payload for convenience (gateway can also join).
        payload = []
        for rec in recs:
            payload.append(
                {
                    "recommendation": RecommendationSerializer(rec).data,
                    "book": book_by_id.get(rec.recommended_book_id),
                }
            )

        return Response(
            {"customer_id": customer_id, "recommendations": payload, "source": "generated"},
            status=status.HTTP_200_OK,
        )
