from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('app', '0001_initial')]
    operations = [
        migrations.AddField(model_name='book', name='description', field=models.TextField(blank=True, null=True)),
        migrations.AddField(model_name='book', name='cover_image_url', field=models.URLField(blank=True, null=True)),
    ]
