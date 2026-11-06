from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0019_complete_request_event_choices')]

    operations = [
        migrations.CreateModel(
            name='PublicRequestRateBucket',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fingerprint', models.CharField(max_length=64)),
                ('window_started_at', models.DateTimeField()),
                ('attempts', models.PositiveIntegerField(default=0)),
            ],
            options={
                'indexes': [models.Index(fields=['window_started_at'], name='core_public_window__73ce44_idx')],
                'constraints': [models.UniqueConstraint(fields=('fingerprint', 'window_started_at'), name='unique_public_request_rate_bucket')],
            },
        ),
    ]
