from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0009_request_completion_review'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ExtraWork',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=180, verbose_name='Дополнительная работа')),
                ('price', models.DecimalField(decimal_places=0, max_digits=10, verbose_name='Стоимость, ₽')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Добавлена')),
                ('added_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('service_request', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='extra_works', to='core.servicerequest')),
            ],
            options={'verbose_name': 'Дополнительная работа', 'verbose_name_plural': 'Дополнительные работы', 'ordering': ['created_at', 'id']},
        ),
    ]
