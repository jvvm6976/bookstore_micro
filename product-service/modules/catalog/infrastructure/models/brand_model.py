from django.db import models


class Brand(models.Model):
    slug = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=120)
    country = models.CharField(max_length=120, blank=True, default='')

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name
