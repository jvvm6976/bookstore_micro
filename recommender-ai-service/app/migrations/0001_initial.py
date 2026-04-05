# Generated manually for initial schema

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="CustomerBookInteraction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("customer_id", models.IntegerField()),
                ("book_id", models.IntegerField()),
                ("interaction_type", models.CharField(max_length=50)),
                ("rating", models.IntegerField(blank=True, null=True)),
                ("timestamp", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-timestamp"],
                "unique_together": {("customer_id", "book_id", "interaction_type")},
            },
        ),
        migrations.CreateModel(
            name="Recommendation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("customer_id", models.IntegerField()),
                ("recommended_book_id", models.IntegerField()),
                ("score", models.FloatField(default=0)),
                ("reason", models.CharField(blank=True, max_length=500, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("clicked", models.BooleanField(default=False)),
            ],
            options={"ordering": ["-score"]},
        ),
    ]

