from django.db import models
from django.contrib.auth.models import AbstractUser

class Address(models.Model):
    street = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100)

class Job(models.Model):
    title = models.CharField(max_length=100)
    company = models.CharField(max_length=100)

class Customer(AbstractUser):
    address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True, blank=True)
    job = models.ForeignKey(Job, on_delete=models.SET_NULL, null=True, blank=True)
    cart_id = models.IntegerField(null=True, blank=True) 

    groups = models.ManyToManyField('auth.Group', related_name='customer_groups', blank=True)
    user_permissions = models.ManyToManyField('auth.Permission', related_name='customer_permissions', blank=True)