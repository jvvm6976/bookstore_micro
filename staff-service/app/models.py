from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser


class Role(models.TextChoices):
    ADMIN = 'admin', 'Administrator'
    MANAGER = 'manager', 'Manager'
    INVENTORY = 'inventory', 'Inventory'
    SHIPPING = 'shipping', 'Shipping'
    STAFF = 'staff', 'Staff'


class PermissionType(models.TextChoices):
    # 15 granular permissions
    VIEW_DASHBOARD = 'view_dashboard', 'View dashboard'
    VIEW_ANALYTICS = 'view_analytics', 'View analytics'
    VIEW_AUDIT_LOG = 'view_audit_log', 'View audit log'

    MANAGE_BOOKS = 'manage_books', 'Manage books'
    MANAGE_INVENTORY = 'manage_inventory', 'Manage inventory'
    MANAGE_ORDERS = 'manage_orders', 'Manage orders'
    UPDATE_ORDER_STATUS = 'update_order_status', 'Update order status'

    MANAGE_PAYMENTS = 'manage_payments', 'Manage payments'
    PROCESS_REFUNDS = 'process_refunds', 'Process refunds'

    MANAGE_SHIPMENTS = 'manage_shipments', 'Manage shipments'

    MANAGE_CUSTOMERS = 'manage_customers', 'Manage customers'
    MANAGE_STAFF = 'manage_staff', 'Manage staff'
    MANAGE_SHIFTS = 'manage_shifts', 'Manage shifts'
    VIEW_SHIFTS = 'view_shifts', 'View shifts'

    MANAGE_ROLES = 'manage_roles', 'Manage roles'


class Staff(AbstractUser):
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STAFF)
    department = models.CharField(max_length=100, blank=True)
    
    def is_admin(self):
        return self.role == Role.ADMIN
    
    def is_manager(self):
        return self.role in [Role.ADMIN, Role.MANAGER]
    
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"


class ActivityLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="activity_logs"
    )
    action = models.CharField(max_length=100)
    resource_type = models.CharField(max_length=100, blank=True, default="")
    resource_id = models.CharField(max_length=100, blank=True, default="")
    message = models.CharField(max_length=500, blank=True, default="")
    meta = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class ShiftStatus(models.TextChoices):
    SCHEDULED = "scheduled", "Scheduled"
    STARTED = "started", "Started"
    ENDED = "ended", "Ended"
    CANCELLED = "cancelled", "Cancelled"


class Shift(models.Model):
    staff = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="shifts")
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=ShiftStatus.choices, default=ShiftStatus.SCHEDULED)
    notes = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_time"]
