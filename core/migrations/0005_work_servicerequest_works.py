from django.db import migrations, models
import django.db.models.deletion


def create_initial_works(apps, schema_editor):
    SubCategory = apps.get_model('core', 'SubCategory')
    Work = apps.get_model('core', 'Work')

    for service in SubCategory.objects.all():
        base_price = int(service.approximate_price)
        if service.name == 'Смеситель':
            items = [
                ('Установка нового смесителя', 1000),
                ('Замена картриджа', 500),
                ('Прочистка аэратора', 500),
                ('Замена гибких шлангов', 500),
            ]
        else:
            items = [
                (f'Диагностика: {service.name}', max(500, round(base_price * 0.25 / 100) * 100)),
                (f'Ремонт: {service.name}', max(500, round(base_price * 0.6 / 100) * 100)),
                (f'Установка или замена: {service.name}', base_price),
            ]

        for order, (name, price) in enumerate(items):
            Work.objects.create(
                service=service,
                name=name,
                price=price,
                sort_order=order,
                is_active=True,
            )


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0004_assign_service_images'),
    ]

    operations = [
        migrations.CreateModel(
            name='Work',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=180, verbose_name='Название работы')),
                ('description', models.TextField(blank=True, verbose_name='Подробное описание')),
                ('price', models.DecimalField(decimal_places=0, max_digits=10, verbose_name='Стоимость, ₽')),
                ('sort_order', models.PositiveIntegerField(default=0, verbose_name='Порядок')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активна')),
                ('service', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='works', to='core.subcategory', verbose_name='Услуга')),
            ],
            options={
                'verbose_name': 'Работа',
                'verbose_name_plural': 'Работы',
                'ordering': ['sort_order', 'name'],
            },
        ),
        migrations.AddField(
            model_name='servicerequest',
            name='works',
            field=models.ManyToManyField(blank=True, related_name='service_requests', to='core.work', verbose_name='Выбранные работы'),
        ),
        migrations.RunPython(create_initial_works, migrations.RunPython.noop),
    ]
