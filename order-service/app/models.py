from django.db import models

class Order(models.Model):
    user_id = models.IntegerField()
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    current_status = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'orders'

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product_id = models.IntegerField()
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = 'order_items'

class OrderAddress(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='address')
    receiver_name = models.CharField(max_length=100)
    full_address = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)

    class Meta:
        db_table = 'order_addresses'

class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_histories')
    status = models.CharField(max_length=50)
    updated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'order_status_histories'
