from django.db import models


class ProductType(models.Model):
    slug = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=120)
    icon = models.CharField(max_length=16, default='📦')

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name
