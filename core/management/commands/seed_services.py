from django.core.management.base import BaseCommand
from django.utils.text import slugify

from core.models import Category, SubCategory


SAMPLE = [
    {
        'name': 'Кухня',
        'description': 'Ремонт и установка кухонной сантехники',
        'subs': [
            ('Смеситель', 2500),
            ('Мойка', 3000),
            ('Посудомоечная машина', 4500),
            ('Фильтр для воды', 2000),
        ],
    },
    {
        'name': 'Ванная',
        'description': 'Сантехника и инженерные системы ванной комнаты',
        'subs': [
            ('Смеситель', 2500),
            ('Унитаз', 3500),
            ('Ванна / душевая кабина', 5000),
            ('Водонагреватель', 4000),
            ('Сифон / канализация', 2200),
        ],
    },
    {
        'name': 'Отопление',
        'description': 'Обслуживание систем отопления',
        'subs': [
            ('Радиатор', 3500),
            ('Системы отопления', 6000),
            ('Тёплый пол', 5500),
            ('Насос', 3200),
        ],
    },
    {
        'name': 'Водоснабжение',
        'description': 'Водопровод, давление, протечки',
        'subs': [
            ('Смеситель', 2500),
            ('Трубы / протечки', 3000),
            ('Водонагреватель', 4000),
            ('Насосная станция', 5000),
            ('Счётчики воды', 1800),
        ],
    },
    {
        'name': 'Канализация',
        'description': 'Засоры и ремонт канализационных систем',
        'subs': [
            ('Прочистка засоров', 2800),
            ('Сифон / канализация', 2200),
            ('Унитаз', 3500),
        ],
    },
]


class Command(BaseCommand):
    help = 'Заполняет демо-категории и подкатегории услуг'

    def handle(self, *args, **options):
        created_categories = 0
        created_subs = 0

        for index, item in enumerate(SAMPLE):
            category, was_created = Category.objects.get_or_create(
                slug=slugify(item['name'], allow_unicode=True),
                defaults={
                    'name': item['name'],
                    'description': item['description'],
                    'sort_order': index,
                    'is_active': True,
                },
            )
            if was_created:
                created_categories += 1

            for sub_index, (sub_name, price) in enumerate(item['subs']):
                _, sub_created = SubCategory.objects.get_or_create(
                    category=category,
                    name=sub_name,
                    defaults={
                        'approximate_price': price,
                        'sort_order': sub_index,
                        'is_active': True,
                    },
                )
                if sub_created:
                    created_subs += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Готово: категорий +{created_categories}, подкатегорий +{created_subs}'
            )
        )
