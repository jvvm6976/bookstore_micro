from django.db import models
from django.contrib.auth.hashers import make_password, check_password as django_check_password


class UserRole(models.TextChoices):
    CUSTOMER = 'customer', 'Customer'
    STAFF = 'staff', 'Staff'
    MANAGER = 'manager', 'Manager'
    ADMIN = 'admin', 'Admin'


class AuthUser(models.Model):
    """Central auth user – mirrors identity across services."""
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=255)
    role = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.CUSTOMER)
    service_user_id = models.IntegerField(null=True, blank=True)  # ID in the domain service
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)

    def set_password(self, raw_password):
        self.password_hash = make_password(raw_password)

    def check_password(self, raw_password):
        return django_check_password(raw_password, self.password_hash)

    def __str__(self):
        return f"{self.username} ({self.role})"


class RevokedToken(models.Model):
    """Blacklist for logged-out JWTs (jti claim)."""
    jti = models.CharField(max_length=64, unique=True)
    revoked_at = models.DateTimeField(auto_now_add=True)
