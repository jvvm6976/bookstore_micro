from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='address',
            name='customer',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='addresses', to='app.customer'),
        ),
        migrations.AddField(
            model_name='address',
            name='is_default',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='address',
            name='label',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='address',
            name='phone_number',
            field=models.CharField(default='', max_length=20),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='address',
            name='recipient_name',
            field=models.CharField(blank=True, default='', max_length=120),
        ),
        migrations.AddField(
            model_name='address',
            name='ward',
            field=models.CharField(default='', max_length=120),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='address',
            name='country',
            field=models.CharField(default='Viet Nam', max_length=100),
        ),
        migrations.AddField(
            model_name='customer',
            name='phone_number',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
        migrations.AddIndex(
            model_name='address',
            index=models.Index(fields=['customer', 'is_default'], name='app_address_custome_80f2e6_idx'),
        ),
    ]
