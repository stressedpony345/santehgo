from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0002_servicerequest_quote_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='subcategory',
            name='description',
            field=models.TextField(blank=True, help_text='Коротко опишите услугу. Если оставить пустым, будет показано описание категории.', verbose_name='Описание карточки'),
        ),
        migrations.AddField(
            model_name='subcategory',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to='services/', verbose_name='Изображение карточки'),
        ),
    ]
