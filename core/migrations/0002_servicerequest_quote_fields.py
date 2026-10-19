from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='servicerequest',
            name='address',
            field=models.CharField(blank=True, max_length=240, verbose_name='Адрес'),
        ),
        migrations.AddField(
            model_name='servicerequest',
            name='issue',
            field=models.CharField(blank=True, max_length=200, verbose_name='Что случилось'),
        ),
        migrations.AddField(
            model_name='servicerequest',
            name='preferred_time',
            field=models.CharField(blank=True, max_length=80, verbose_name='Когда удобно'),
        ),
        migrations.AlterField(
            model_name='servicerequest',
            name='full_name',
            field=models.CharField(blank=True, max_length=200, verbose_name='ФИО'),
        ),
        migrations.AlterField(
            model_name='servicerequest',
            name='subcategories',
            field=models.ManyToManyField(
                blank=True,
                related_name='service_requests',
                to='core.subcategory',
                verbose_name='Выбранные услуги',
            ),
        ),
    ]
