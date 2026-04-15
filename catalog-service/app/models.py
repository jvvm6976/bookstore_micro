from django.db import models

class BookCatalog(models.Model):
    """Cached copy of book data from book-service"""
    book_id = models.IntegerField(unique=True)
    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255, null=True, blank=True)
    publisher = models.CharField(max_length=255, null=True, blank=True)
    category = models.CharField(max_length=50)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.IntegerField(default=0)
    description = models.TextField(null=True, blank=True)
    cover_image_url = models.URLField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    average_rating = models.FloatField(default=0)
    total_reviews = models.IntegerField(default=0)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class SearchHistory(models.Model):
    """Track user search behavior for recommendations"""
    customer_id = models.IntegerField()
    search_query = models.CharField(max_length=500)
    search_count = models.IntegerField(default=1)
    category = models.CharField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('customer_id', 'search_query')

    def __str__(self):
        return f"Customer {self.customer_id} searched: {self.search_query}"
