from django.db import models

from .brand_model import Brand
from .category_model import Category
from .product_type_model import ProductType
from ..querysets.product_queryset import ProductQuerySet


class Product(models.Model):
    objects = ProductQuerySet.as_manager()

    slug = models.SlugField(max_length=150, unique=True)
    name = models.CharField(max_length=255)
    author = models.CharField(max_length=255, null=True, blank=True)
    product_type = models.ForeignKey(ProductType, on_delete=models.PROTECT, related_name='products')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    price = models.DecimalField(max_digits=12, decimal_places=2)
    stock = models.IntegerField(default=0)
    description = models.TextField(null=True, blank=True)
    cover_image_url = models.URLField(null=True, blank=True)
    attributes = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name
