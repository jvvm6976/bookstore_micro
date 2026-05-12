from django.db import models
from django.contrib.auth.models import AbstractUser

class Role(models.Model):
    role_name = models.CharField(max_length=50, unique=True)

    class Meta:
        db_table = 'roles'

class User(AbstractUser):
    # AbstractUser provides username, password, email, first_name, last_name
    phone = models.CharField(max_length=20, unique=True, null=True, blank=True)
    role = models.ForeignKey(Role, on_delete=models.RESTRICT, null=True)

    class Meta:
        db_table = 'users'

class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    receiver_name = models.CharField(max_length=100)
    street = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'addresses'
