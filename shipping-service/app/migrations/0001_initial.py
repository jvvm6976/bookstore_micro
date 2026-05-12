from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Shipment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order_id', models.IntegerField(unique=True)),
                ('receiver_name', models.CharField(max_length=100)),
                ('phone', models.CharField(max_length=20)),
                ('full_address', models.TextField()),
                ('current_status', models.CharField(
                    choices=[('processing', 'Processing'), ('shipping', 'Shipping'), ('delivered', 'Delivered')],
                    default='processing',
                    max_length=50,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'db_table': 'shipments'},
        ),
        migrations.CreateModel(
            name='ShipmentTracking',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('shipment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='trackings', to='app.shipment')),
                ('location', models.CharField(blank=True, max_length=255, null=True)),
                ('status', models.CharField(max_length=50)),
                ('updated_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'db_table': 'shipment_trackings'},
        ),
    ]
