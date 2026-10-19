from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def mark_existing_processed_as_approved(apps, schema_editor):
    ServiceRequest = apps.get_model('core', 'ServiceRequest')
    ServiceRequest.objects.filter(is_processed=True).update(completion_status='approved')


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0008_master_app'),
    ]

    operations = [
        migrations.AddField(
            model_name='servicerequest',
            name='completion_status',
            field=models.CharField(choices=[('none', 'Не отправлена'), ('pending', 'На рассмотрении'), ('approved', 'Завершена'), ('rejected', 'Отклонена')], db_index=True, default='none', max_length=16, verbose_name='Статус завершения'),
        ),
        migrations.AddField(
            model_name='servicerequest',
            name='completion_photo',
            field=models.ImageField(blank=True, null=True, upload_to='completed/%Y/%m/', verbose_name='Фото выполненной работы'),
        ),
        migrations.AddField(
            model_name='servicerequest',
            name='completion_requested_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Отправлена на модерацию'),
        ),
        migrations.AddField(
            model_name='servicerequest',
            name='completion_reviewed_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Проверена администратором'),
        ),
        migrations.AddField(
            model_name='servicerequest',
            name='completion_reviewed_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_service_requests', to=settings.AUTH_USER_MODEL, verbose_name='Проверил'),
        ),
        migrations.RunPython(mark_existing_processed_as_approved, migrations.RunPython.noop),
    ]
