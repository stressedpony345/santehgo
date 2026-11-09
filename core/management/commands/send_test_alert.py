from django.core.management.base import BaseCommand, CommandError

from core.monitoring import send_error_alert


class Command(BaseCommand):
    help = 'Отправить тестовую production-тревогу владельцу.'

    def handle(self, *args, **options):
        delivered = send_error_alert('Тестовая тревога SantehGo', {'kind': 'manual_test'})
        if not delivered:
            raise CommandError('Тестовая тревога не доставлена.')
        self.stdout.write(self.style.SUCCESS('Тестовая тревога доставлена.'))
