# Generated manually for initial schema

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Manager",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("password", models.CharField(max_length=255)),
                ("department", models.CharField(blank=True, max_length=100, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="SalesReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("period", models.CharField(max_length=50)),
                ("total_orders", models.IntegerField(default=0)),
                ("total_revenue", models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ("total_items_sold", models.IntegerField(default=0)),
                ("top_book_id", models.IntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("report_date", models.DateField()),
            ],
        ),
        migrations.CreateModel(
            name="InventoryLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("book_id", models.IntegerField()),
                ("book_title", models.CharField(blank=True, max_length=255, null=True)),
                ("previous_stock", models.IntegerField()),
                ("new_stock", models.IntegerField()),
                ("change_amount", models.IntegerField()),
                ("reason", models.CharField(max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="app.manager",
                    ),
                ),
            ],
        ),
    ]

