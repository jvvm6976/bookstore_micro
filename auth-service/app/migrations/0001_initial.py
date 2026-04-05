from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name='AuthUser',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('username', models.CharField(max_length=150, unique=True)),
                ('email', models.EmailField(unique=True)),
                ('password_hash', models.CharField(max_length=255)),
                ('role', models.CharField(max_length=20, default='customer')),
                ('service_user_id', models.IntegerField(null=True, blank=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_login', models.DateTimeField(null=True, blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='RevokedToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('jti', models.CharField(max_length=64, unique=True)),
                ('revoked_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
