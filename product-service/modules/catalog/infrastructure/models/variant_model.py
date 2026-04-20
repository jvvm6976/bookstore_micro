from django.db import models

from .product_model import Product


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    sku = models.CharField(max_length=80, unique=True)
    label = models.CharField(max_length=120, blank=True, default='')
    color = models.CharField(max_length=60, blank=True, default='')
    size = models.CharField(max_length=60, blank=True, default='')
    price_delta = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    stock = models.IntegerField(default=0)
    attributes = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.sku
