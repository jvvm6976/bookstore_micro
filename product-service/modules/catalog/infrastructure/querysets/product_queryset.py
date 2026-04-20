from django.db import models
from django.db.models import Q


class ProductQuerySet(models.QuerySet):
    def apply_filters(self, params):
        queryset = self.select_related('product_type', 'category', 'brand').prefetch_related('variants')
        term = params.get('q') or params.get('search')
        if term:
            queryset = queryset.filter(
                Q(name__icontains=term) |
                Q(author__icontains=term) |
                Q(description__icontains=term) |
                Q(attributes__icontains=term)
            )
        product_type = params.get('type') or params.get('product_type')
        if product_type:
            queryset = queryset.filter(product_type__slug=product_type)
        category = params.get('category')
        if category:
            queryset = queryset.filter(category__slug=category)
        brand = params.get('brand')
        if brand:
            queryset = queryset.filter(brand__slug=brand)
        min_price = params.get('min_price')
        if min_price not in (None, ''):
            queryset = queryset.filter(price__gte=min_price)
        max_price = params.get('max_price')
        if max_price not in (None, ''):
            queryset = queryset.filter(price__lte=max_price)
        in_stock = params.get('in_stock')
        if in_stock in ('1', 'true', 'True', 'yes'):
            queryset = queryset.filter(stock__gt=0)
        return queryset
