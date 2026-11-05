import uuid

from django.db import migrations, models


def populate_public_tokens(apps, schema_editor):
    ServiceRequest = apps.get_model('core', 'ServiceRequest')
    for request in ServiceRequest.objects.filter(public_token__isnull=True).iterator():
        request.public_token = uuid.uuid4()
        request.save(update_fields=('public_token',))


class Migration(migrations.Migration):
    dependencies = [('core', '0012_servicerequest_payment_confirmed_at_and_more')]

    operations = [
        migrations.AddField(
            model_name='servicerequest',
            name='idempotency_key',
            field=models.CharField(blank=True, editable=False, max_length=64, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='servicerequest',
            name='idempotency_hash',
            field=models.CharField(blank=True, editable=False, max_length=64),
        ),
        migrations.AddField(
            model_name='servicerequest',
            name='consented_at',
            field=models.DateTimeField(blank=True, editable=False, null=True, verbose_name='Согласие получено'),
        ),
        migrations.AddField(
            model_name='servicerequest',
            name='consent_version',
            field=models.CharField(blank=True, editable=False, max_length=20),
        ),
        migrations.AddField(
            model_name='servicerequest',
            name='callback_requested_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Клиент запросил звонок'),
        ),
        migrations.AddField(
            model_name='servicerequest',
            name='cancel_requested_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Клиент запросил отмену'),
        ),
        migrations.AddField(
            model_name='servicerequest',
            name='public_token',
            field=models.UUIDField(null=True, editable=False),
        ),
        migrations.RunPython(populate_public_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='servicerequest',
            name='public_token',
            field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
