from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

class Comment(models.Model):
    customer_id = models.IntegerField()
    book_id = models.IntegerField()
    order_id = models.IntegerField(db_index=True)
    content = models.TextField()
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        default=5
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    helpful_count = models.IntegerField(default=0)

    class Meta:
        unique_together = ('customer_id', 'book_id', 'order_id')

    def __str__(self):
        return (
            f"Comment by Customer {self.customer_id} on Book {self.book_id} "
            f"(Order {self.order_id}) - Rating {self.rating}"
        )
