from django.db import models

class Domain(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'domains'

class Category(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, related_name='categories')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'categories'
        unique_together = ('name', 'domain')

class Product(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    sku = models.CharField(max_length=100, unique=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    stock = models.IntegerField(default=0)
    status = models.CharField(max_length=50, default='active')
    image_url = models.CharField(max_length=500, null=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.RESTRICT, related_name='products')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'products'

class Book(models.Model):
    product = models.OneToOneField(Product, on_delete=models.CASCADE, primary_key=True)
    author = models.CharField(max_length=255)
    publisher = models.CharField(max_length=255)
    isbn = models.CharField(max_length=20, unique=True)

    class Meta:
        db_table = 'book'

class Electronics(models.Model):
    product = models.OneToOneField(Product, on_delete=models.CASCADE, primary_key=True)
    brand = models.CharField(max_length=100)
    warranty_months = models.IntegerField(default=0)

    class Meta:
        db_table = 'electronics'

class Fashion(models.Model):
    product = models.OneToOneField(Product, on_delete=models.CASCADE, primary_key=True)
    size = models.CharField(max_length=10)
    color = models.CharField(max_length=50)

    class Meta:
        db_table = 'fashion'
