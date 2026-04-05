from django.db import models

class CustomerBookInteraction(models.Model):
    """Track customer interactions with books"""
    customer_id = models.IntegerField()
    book_id = models.IntegerField()
    interaction_type = models.CharField(max_length=50)  # view, cart, purchase, rate
    rating = models.IntegerField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('customer_id', 'book_id', 'interaction_type')
        ordering = ['-timestamp']

    def __str__(self):
        return f"Customer {self.customer_id} - Book {self.book_id} - {self.interaction_type}"


class Recommendation(models.Model):
    """Store generated recommendations"""
    customer_id = models.IntegerField()
    recommended_book_id = models.IntegerField()
    score = models.FloatField(default=0)  # Confidence score
    reason = models.CharField(max_length=500, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    clicked = models.BooleanField(default=False)

    class Meta:
        ordering = ['-score']

    def __str__(self):
        return f"Recommend Book {self.recommended_book_id} to Customer {self.customer_id}"
