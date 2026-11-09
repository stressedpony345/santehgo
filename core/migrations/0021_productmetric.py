from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0020_publicrequestratebucket')]

    operations = [
        migrations.CreateModel(
            name='ProductMetric',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('day', models.DateField()),
                ('event', models.CharField(choices=[('quote_started', 'Быстрая форма начата'), ('catalog_started', 'Каталог открыт'), ('contacts_opened', 'Контакты открыты'), ('request_created', 'Заявка создана')], max_length=24)),
                ('count', models.PositiveIntegerField(default=0)),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('day', 'event'), name='unique_product_metric_day_event')],
            },
        ),
    ]
