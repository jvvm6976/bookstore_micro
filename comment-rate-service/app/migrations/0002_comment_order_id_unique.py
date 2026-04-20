from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="comment",
            name="order_id",
            field=models.IntegerField(db_index=True, default=0),
            preserve_default=False,
        ),
        migrations.AlterUniqueTogether(
            name="comment",
            unique_together={("customer_id", "book_id", "order_id")},
        ),
    ]
