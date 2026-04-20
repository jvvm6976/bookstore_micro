from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0002_customer_address_profile_upgrade'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customer',
            name='address',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='primary_for_customers',
                related_query_name='primary_customer',
                to='app.address',
            ),
        ),
    ]
