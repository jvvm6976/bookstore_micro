# Generated manually for initial schema

from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Comment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("customer_id", models.IntegerField()),
                ("book_id", models.IntegerField()),
                ("content", models.TextField()),
                (
                    "rating",
                    models.IntegerField(
                        default=5,
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(5),
                        ],
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("helpful_count", models.IntegerField(default=0)),
            ],
            options={"unique_together": {("customer_id", "book_id")}},
        ),
    ]

