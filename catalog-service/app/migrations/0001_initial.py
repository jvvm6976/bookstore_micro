# Generated manually for initial schema

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="BookCatalog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("book_id", models.IntegerField(unique=True)),
                ("title", models.CharField(max_length=255)),
                ("author", models.CharField(blank=True, max_length=255, null=True)),
                ("publisher", models.CharField(blank=True, max_length=255, null=True)),
                ("category", models.CharField(max_length=50)),
                ("price", models.DecimalField(decimal_places=2, max_digits=10)),
                ("stock", models.IntegerField(default=0)),
                ("description", models.TextField(blank=True, null=True)),
                ("cover_image_url", models.URLField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("average_rating", models.FloatField(default=0)),
                ("total_reviews", models.IntegerField(default=0)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="SearchHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("customer_id", models.IntegerField()),
                ("search_query", models.CharField(max_length=500)),
                ("search_count", models.IntegerField(default=1)),
                ("category", models.CharField(blank=True, max_length=50, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"unique_together": {("customer_id", "search_query")}},
        ),
    ]

