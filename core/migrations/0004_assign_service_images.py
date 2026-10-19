from django.db import migrations


IMAGES = {
    ('Кухня', 'Смеситель'): 'services/kitchen-faucet.png',
    ('Кухня', 'Мойка'): 'services/kitchen-sink.png',
    ('Кухня', 'Посудомоечная машина'): 'services/kitchen-dishwasher.png',
    ('Кухня', 'Фильтр для воды'): 'services/kitchen-filter.png',
    ('Ванная', 'Смеситель'): 'services/bathroom-faucet.png',
    ('Ванная', 'Унитаз'): 'services/bathroom-toilet.png',
    ('Ванная', 'Ванна / душевая кабина'): 'services/bathroom-shower.png',
    ('Ванная', 'Водонагреватель'): 'services/bathroom-heater.png',
    ('Ванная', 'Сифон / канализация'): 'services/bathroom-siphon.png',
    ('Отопление', 'Радиатор'): 'services/heating-radiator.png',
    ('Отопление', 'Системы отопления'): 'services/heating-system.png',
    ('Отопление', 'Тёплый пол'): 'services/heating-floor.png',
    ('Отопление', 'Насос'): 'services/heating-pump.png',
    ('Водоснабжение', 'Смеситель'): 'services/water-faucet.png',
    ('Водоснабжение', 'Трубы / протечки'): 'services/water-pipes.png',
    ('Водоснабжение', 'Водонагреватель'): 'services/water-heater.png',
    ('Водоснабжение', 'Насосная станция'): 'services/water-pump-station.png',
    ('Водоснабжение', 'Счётчики воды'): 'services/water-meters.png',
    ('Канализация', 'Прочистка засоров'): 'services/sewer-clog.png',
    ('Канализация', 'Сифон / канализация'): 'services/sewer-siphon.png',
    ('Канализация', 'Унитаз'): 'services/sewer-toilet.png',
}


def assign_images(apps, schema_editor):
    SubCategory = apps.get_model('core', 'SubCategory')
    for (category_name, service_name), image_path in IMAGES.items():
        SubCategory.objects.filter(
            category__name=category_name,
            name=service_name,
        ).update(image=image_path)


def clear_generated_images(apps, schema_editor):
    SubCategory = apps.get_model('core', 'SubCategory')
    SubCategory.objects.filter(image__in=IMAGES.values()).update(image='')


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0003_subcategory_description_image'),
    ]

    operations = [
        migrations.RunPython(assign_images, clear_generated_images),
    ]
