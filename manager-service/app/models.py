from django.db import models

class Manager(models.Model):
    """Manager user accounts"""
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)
    department = models.CharField(max_length=100, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.email}"


class InventoryLog(models.Model):
    """Log inventory changes"""
    book_id = models.IntegerField()
    book_title = models.CharField(max_length=255, null=True, blank=True)
    previous_stock = models.IntegerField()
    new_stock = models.IntegerField()
    change_amount = models.IntegerField()
    reason = models.CharField(max_length=500)
    created_by = models.ForeignKey(Manager, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Book {self.book_id}: {self.previous_stock} -> {self.new_stock}"


class SalesReport(models.Model):
    """Generate sales reports"""
    period = models.CharField(max_length=50)  # daily, weekly, monthly
    total_orders = models.IntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_items_sold = models.IntegerField(default=0)
    top_book_id = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    report_date = models.DateField()

    def __str__(self):
        return f"{self.period} - {self.report_date}"
