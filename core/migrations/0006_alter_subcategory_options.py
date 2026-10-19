from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0005_work_servicerequest_works'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='subcategory',
            options={
                'ordering': ['sort_order', 'name'],
                'verbose_name': 'Услуга',
                'verbose_name_plural': 'Услуги',
            },
        ),
    ]
