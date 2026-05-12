"""CommentRateServiceClient.

Comment-service actual endpoints:
  GET  /reviews/                        — list all approved reviews
  GET  /reviews/products/<pk>/          — reviews by product_id
  GET  /reviews/orders/<pk>/            — reviews by order_id

Review serializer fields:
  id, user_id, product_id, order_id, rating, comment,
  status, created_at, updated_at, replies
"""
from __future__ import annotations
from .base import ServiceClient, _extract_list
from ..core.config import COMMENT_SERVICE_URL


class CommentRateServiceClient(ServiceClient):
    def __init__(self):
        super().__init__(COMMENT_SERVICE_URL, "comment-rate-service")

    def get_reviews_by_product(self, product_id: int) -> dict:
        """GET /reviews/products/<product_id>/ — approved reviews for one product."""
        data = self.get(f"/reviews/products/{product_id}/")
        if not data:
            return {"comments": [], "average_rating": 0, "total_reviews": 0}
        reviews = _extract_list(data)
        if reviews:
            avg = sum(float(r.get("rating") or 0) for r in reviews) / len(reviews)
        else:
            avg = 0.0
        return {
            "comments": reviews,
            "average_rating": round(avg, 2),
            "total_reviews": len(reviews),
        }

    def get_reviews_for_products(self, product_ids: list[int]) -> dict[int, dict]:
        """Batch fetch ratings. Returns {product_id: {avg, count}}.

        Calls GET /reviews/ (all approved reviews) and filters client-side.
        """
        all_data = self.get("/reviews/")
        comments = _extract_list(all_data)
        from collections import defaultdict
        stats: dict[int, dict] = defaultdict(lambda: {"sum": 0.0, "count": 0})
        for c in comments:
            # comment-service uses product_id (not book_id)
            pid = c.get("product_id")
            r   = c.get("rating")
            if pid in product_ids and r is not None:
                stats[pid]["sum"]   += float(r)
                stats[pid]["count"] += 1
        return {
            pid: {
                "avg":   s["sum"] / s["count"] if s["count"] else 0.0,
                "count": s["count"],
            }
            for pid, s in stats.items()
        }

    def get_all_comments(self) -> list[dict]:
        """GET /reviews/ — all approved reviews."""
        data = self.get("/reviews/")
        return _extract_list(data)


comment_client = CommentRateServiceClient()
