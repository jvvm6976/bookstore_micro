from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="CustomerBookInteraction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("customer_id", models.IntegerField(db_index=True)),
                ("book_id", models.IntegerField(db_index=True)),
                ("interaction_type", models.CharField(max_length=50)),
                ("rating", models.IntegerField(blank=True, null=True)),
                ("count", models.PositiveIntegerField(default=1)),
                ("timestamp", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["-timestamp"], "unique_together": {("customer_id", "book_id", "interaction_type")}},
        ),
    ]
