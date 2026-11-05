from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [('core', '0013_servicerequest_public_access')]

    operations = [
        migrations.CreateModel(
            name='ClientNotification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event', models.CharField(choices=[('created', 'Заявка создана'), ('assigned', 'Мастер назначен'), ('started', 'Работа начата'), ('completed', 'Работа завершена'), ('cancel_requested', 'Запрошена отмена')], max_length=32, verbose_name='Событие')),
                ('dedupe_key', models.CharField(max_length=120, unique=True, verbose_name='Ключ события')),
                ('channel', models.CharField(default='sms', max_length=16, verbose_name='Канал')),
                ('destination', models.CharField(max_length=32, verbose_name='Получатель')),
                ('template_version', models.CharField(default='1', max_length=20, verbose_name='Версия шаблона')),
                ('status', models.CharField(choices=[('pending', 'Ожидает отправки'), ('sending', 'Отправляется'), ('sent', 'Отправлено'), ('failed', 'Ошибка, будет повторено'), ('dead', 'Не доставлено')], db_index=True, default='pending', max_length=12, verbose_name='Статус')),
                ('attempts', models.PositiveSmallIntegerField(default=0, verbose_name='Попыток')),
                ('next_attempt_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Следующая попытка')),
                ('sent_at', models.DateTimeField(blank=True, null=True, verbose_name='Отправлено')),
                ('last_error', models.CharField(blank=True, max_length=240, verbose_name='Последняя ошибка')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создано')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
                ('service_request', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='client_notifications', to='core.servicerequest', verbose_name='Заявка')),
            ],
            options={'verbose_name': 'Уведомление клиенту', 'verbose_name_plural': 'Уведомления клиентам', 'ordering': ('created_at',)},
        ),
    ]
