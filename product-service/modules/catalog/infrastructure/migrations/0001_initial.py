from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Brand',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slug', models.SlugField(max_length=64, unique=True)),
                ('name', models.CharField(max_length=120)),
                ('country', models.CharField(blank=True, default='', max_length=120)),
            ],
            options={'ordering': ['name']},
        ),
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slug', models.SlugField(max_length=64, unique=True)),
                ('name', models.CharField(max_length=120)),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='children', to='catalog.category')),
            ],
            options={'ordering': ['name']},
        ),
        migrations.CreateModel(
            name='ProductType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slug', models.SlugField(max_length=64, unique=True)),
                ('name', models.CharField(max_length=120)),
                ('icon', models.CharField(default='📦', max_length=16)),
            ],
            options={'ordering': ['name']},
        ),
        migrations.CreateModel(
            name='Product',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slug', models.SlugField(max_length=150, unique=True)),
                ('name', models.CharField(max_length=255)),
                ('author', models.CharField(blank=True, max_length=255, null=True)),
                ('price', models.DecimalField(decimal_places=2, max_digits=12)),
                ('stock', models.IntegerField(default=0)),
                ('description', models.TextField(blank=True, null=True)),
                ('cover_image_url', models.URLField(blank=True, null=True)),
                ('attributes', models.JSONField(blank=True, default=dict)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('brand', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='products', to='catalog.brand')),
                ('category', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='products', to='catalog.category')),
                ('product_type', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='products', to='catalog.producttype')),
            ],
            options={'ordering': ['name']},
        ),
        migrations.CreateModel(
            name='ProductVariant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sku', models.CharField(max_length=80, unique=True)),
                ('label', models.CharField(blank=True, default='', max_length=120)),
                ('color', models.CharField(blank=True, default='', max_length=60)),
                ('size', models.CharField(blank=True, default='', max_length=60)),
                ('price_delta', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('stock', models.IntegerField(default=0)),
                ('attributes', models.JSONField(blank=True, default=dict)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='variants', to='catalog.product')),
            ],
            options={'ordering': ['id']},
        ),
    ]
