from django.db import models

class Category(models.TextChoices):
    HISTORY = 'history', 'History'
    MATH = 'math', 'Mathematics'
    SCIENCE = 'science', 'Science'
    FICTION = 'fiction', 'Fiction'
    PROGRAMMING = 'programming', 'Programming'

class Publisher(models.Model):
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)

    def __str__(self):
        return self.name

class Book(models.Model):
    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255, null=True, blank=True)
    publisher = models.ForeignKey(Publisher, on_delete=models.CASCADE, null=True)
    category = models.CharField(max_length=50, choices=Category.choices, default=Category.FICTION)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.IntegerField(default=0)
    description = models.TextField(null=True, blank=True)
    cover_image_url = models.URLField(null=True, blank=True)

    def __str__(self):
        return self.title