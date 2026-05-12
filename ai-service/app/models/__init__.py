"""
Django ORM models for AI Assistant Service.
NOTE: Python loads this package (app/models/) instead of app/models.py
All model definitions live here.
"""
from django.db import models

INTERACTION_WEIGHTS = {
    "view": 1, "search": 2, "cart": 4, "purchase": 8, "rate": 3,
}
PURCHASE_THRESHOLD = 3


class CustomerProductInteraction(models.Model):
    """Track every customer interaction with a product (multi-domain)."""
    customer_id      = models.IntegerField(db_index=True)
    product_id       = models.IntegerField(db_index=True)
    interaction_type = models.CharField(max_length=50)
    rating           = models.IntegerField(null=True, blank=True)
    count            = models.PositiveIntegerField(default=1)
    timestamp        = models.DateTimeField(auto_now=True)
    category         = models.CharField(max_length=100, blank=True, default="")
    price_range      = models.IntegerField(default=2)

    class Meta:
        unique_together = ("customer_id", "product_id", "interaction_type")
        ordering = ["-timestamp"]

    @property
    def weighted_score(self) -> float:
        return INTERACTION_WEIGHTS.get(self.interaction_type, 1) * self.count

    def __str__(self):
        return f"C{self.customer_id}→P{self.product_id} [{self.interaction_type}×{self.count}]"


# Backward-compat alias
CustomerBookInteraction = CustomerProductInteraction
