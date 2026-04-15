from django.db import models

class ShipmentStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    PROCESSING = 'processing', 'Processing'
    SHIPPED = 'shipped', 'Shipped'
    DELIVERED = 'delivered', 'Delivered'
    CANCELLED = 'cancelled', 'Cancelled'

class Shipment(models.Model):
    order_id = models.IntegerField(unique=True)
    status = models.CharField(max_length=20, choices=ShipmentStatus.choices, default=ShipmentStatus.PENDING)
    shipping_address = models.CharField(max_length=500)
    tracking_number = models.CharField(max_length=200, unique=True, null=True, blank=True)
    shipping_method = models.CharField(max_length=50, default='standard')
    estimated_delivery = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Shipment {self.id} - Order {self.order_id} - {self.status}"
