from django.core.management.base import BaseCommand

from core.models import ProductMetric


class Command(BaseCommand):
    help = 'Вывести обезличенные дневные счётчики клиентского пути'

    def handle(self, *args, **options):
        for metric in ProductMetric.objects.order_by('day', 'event'):
            self.stdout.write(f'{metric.day.isoformat()},{metric.event},{metric.count}')
