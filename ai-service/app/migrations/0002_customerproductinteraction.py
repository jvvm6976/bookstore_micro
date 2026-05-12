"""Migration: rename CustomerBookInteraction → CustomerProductInteraction with product_id."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CustomerProductInteraction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('customer_id', models.IntegerField(db_index=True)),
                ('product_id', models.IntegerField(db_index=True)),
                ('interaction_type', models.CharField(max_length=50)),
                ('rating', models.IntegerField(blank=True, null=True)),
                ('count', models.PositiveIntegerField(default=1)),
                ('timestamp', models.DateTimeField(auto_now=True)),
                ('category', models.CharField(blank=True, default='', max_length=100)),
                ('price_range', models.IntegerField(default=2)),
            ],
            options={
                'ordering': ['-timestamp'],
                'unique_together': {('customer_id', 'product_id', 'interaction_type')},
            },
        ),
    ]
