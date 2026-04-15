# Generated manually for initial schema

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Publisher",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("address", models.CharField(max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name="Book",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=255)),
                ("author", models.CharField(blank=True, max_length=255, null=True)),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("history", "History"),
                            ("math", "Mathematics"),
                            ("science", "Science"),
                            ("fiction", "Fiction"),
                            ("programming", "Programming"),
                        ],
                        default="fiction",
                        max_length=50,
                    ),
                ),
                ("price", models.DecimalField(decimal_places=2, max_digits=10)),
                ("stock", models.IntegerField(default=0)),
                (
                    "publisher",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="app.publisher",
                    ),
                ),
            ],
        ),
    ]

