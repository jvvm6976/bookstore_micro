from django.db import models
from django.contrib.auth.models import AbstractUser

class Address(models.Model):
    customer = models.ForeignKey('Customer', related_name='addresses', on_delete=models.CASCADE, null=True, blank=True)
    label = models.CharField(max_length=100, blank=True, default='')
    recipient_name = models.CharField(max_length=120, blank=True, default='')
    phone_number = models.CharField(max_length=20)
    street = models.CharField(max_length=255)
    ward = models.CharField(max_length=120)
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100, default='Viet Nam')
    is_default = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=['customer', 'is_default'])]

    def __str__(self):
        return f"{self.customer_id}:{self.label or self.street}"

class Job(models.Model):
    title = models.CharField(max_length=100)
    company = models.CharField(max_length=100)

class Customer(AbstractUser):
    address = models.ForeignKey(
        Address,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='primary_for_customers',
        related_query_name='primary_customer',
    )
    job = models.ForeignKey(Job, on_delete=models.SET_NULL, null=True, blank=True)
    cart_id = models.IntegerField(null=True, blank=True)
    phone_number = models.CharField(max_length=20, blank=True, default='')

    groups = models.ManyToManyField('auth.Group', related_name='customer_groups', blank=True)
    user_permissions = models.ManyToManyField('auth.Permission', related_name='customer_permissions', blank=True)