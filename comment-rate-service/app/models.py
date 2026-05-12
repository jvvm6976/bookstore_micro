from django.db import models

class Review(models.Model):
    user_id = models.IntegerField()
    product_id = models.IntegerField()
    order_id = models.IntegerField()
    rating = models.IntegerField()
    comment = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=50, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'reviews'
        unique_together = ('user_id', 'product_id', 'order_id')

class ReviewReply(models.Model):
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='replies')
    user_id = models.IntegerField()
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'review_replies'
