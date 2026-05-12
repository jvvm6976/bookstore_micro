from django.db import models


class Shipment(models.Model):
    STATUS_PROCESSING = 'processing'
    STATUS_SHIPPING = 'shipping'
    STATUS_DELIVERED = 'delivered'

    STATUS_CHOICES = [
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_SHIPPING, 'Shipping'),
        (STATUS_DELIVERED, 'Delivered'),
    ]

    order_id = models.IntegerField(unique=True)
    receiver_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    full_address = models.TextField()
    current_status = models.CharField(max_length=50, choices=STATUS_CHOICES, default=STATUS_PROCESSING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'shipments'


class ShipmentTracking(models.Model):
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='trackings')
    location = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=50)
    updated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'shipment_trackings'
