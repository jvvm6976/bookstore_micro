"""
Django ORM models for AI Assistant Service.
Used for persistent interaction tracking and session storage.
FastAPI handles HTTP; Django handles DB via ORM.
"""
from django.db import models

INTERACTION_WEIGHTS = {
    "view": 1, "search": 2, "cart": 4, "purchase": 8, "rate": 3,
}
PURCHASE_THRESHOLD = 3


class CustomerBookInteraction(models.Model):
    """Track every customer interaction with a book."""
    customer_id      = models.IntegerField(db_index=True)
    book_id          = models.IntegerField(db_index=True)
    interaction_type = models.CharField(max_length=50)
    rating           = models.IntegerField(null=True, blank=True)
    count            = models.PositiveIntegerField(default=1)
    timestamp        = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("customer_id", "book_id", "interaction_type")
        ordering = ["-timestamp"]

    @property
    def weighted_score(self) -> float:
        return INTERACTION_WEIGHTS.get(self.interaction_type, 1) * self.count

    def __str__(self):
        return f"C{self.customer_id}→B{self.book_id} [{self.interaction_type}×{self.count}]"
