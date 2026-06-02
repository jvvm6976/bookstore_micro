from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='user_id',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='notification',
            name='recipient_type',
            field=models.CharField(default='customer', max_length=50),
        ),
        migrations.AddField(
            model_name='notification',
            name='target_role',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='notification',
            name='entity_type',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='notification',
            name='entity_id',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='notification',
            name='priority',
            field=models.CharField(default='normal', max_length=20),
        ),
        migrations.CreateModel(
            name='NotificationReadState',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user_id', models.IntegerField()),
                ('status', models.CharField(default='read', max_length=50)),
                ('read_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('notification', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='read_states',
                    to='app.notification',
                )),
            ],
            options={
                'db_table': 'notification_read_states',
                'unique_together': {('notification', 'user_id')},
            },
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['user_id', 'created_at'], name='notificatio_user_id_7336fd_idx'),
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['recipient_type', 'created_at'], name='notificatio_recipie_30e8f7_idx'),
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['type', 'created_at'], name='notificatio_type_cb6908_idx'),
        ),
    ]
