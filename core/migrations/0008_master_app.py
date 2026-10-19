from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0007_alter_servicerequest_issue'),
    ]

    operations = [
        migrations.AddField(
            model_name='servicerequest',
            name='assigned_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Взята в работу'),
        ),
        migrations.AddField(
            model_name='servicerequest',
            name='assigned_to',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_service_requests', to=settings.AUTH_USER_MODEL, verbose_name='Мастер'),
        ),
        migrations.CreateModel(
            name='PushSubscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('endpoint', models.TextField(unique=True, verbose_name='Endpoint')),
                ('p256dh', models.TextField(verbose_name='Ключ p256dh')),
                ('auth', models.TextField(verbose_name='Ключ auth')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создана')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлена')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='push_subscriptions', to=settings.AUTH_USER_MODEL, verbose_name='Мастер')),
            ],
            options={'verbose_name': 'Push-подписка', 'verbose_name_plural': 'Push-подписки'},
        ),
    ]
