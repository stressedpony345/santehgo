from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from core.models import ClientNotification
from core.notifications import deliver_notification


ELIGIBLE_STATUSES = (
    ClientNotification.Status.PENDING,
    ClientNotification.Status.FAILED,
    ClientNotification.Status.SENDING,
)


def claim_notification(notification_id, claim_time=None):
    """Atomically lease an eligible notification to one worker."""
    claim_time = claim_time or timezone.now()
    with transaction.atomic():
        notification = (
            ClientNotification.objects.select_for_update()
            .filter(
                pk=notification_id,
                status__in=ELIGIBLE_STATUSES,
                next_attempt_at__lte=claim_time,
            )
            .first()
        )
        if notification is None:
            return None
        notification.status = ClientNotification.Status.SENDING
        notification.next_attempt_at = claim_time + timedelta(minutes=10)
        notification.save(update_fields=('status', 'next_attempt_at', 'updated_at'))
        return notification


class Command(BaseCommand):
    help = 'Отправляет ограниченную пачку ожидающих клиентских уведомлений.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=50)

    def handle(self, *args, **options):
        if not settings.CLIENT_NOTIFICATIONS_ENABLED:
            self.stdout.write('Клиентские уведомления отключены.')
            return
        limit = options['limit']
        if not 1 <= limit <= 500:
            raise CommandError('limit должен быть от 1 до 500')

        sent = failed = 0
        for notification_id in ClientNotification.objects.filter(
            status__in=ELIGIBLE_STATUSES,
            next_attempt_at__lte=timezone.now(),
        ).values_list('pk', flat=True).order_by('next_attempt_at')[:limit]:
            notification = claim_notification(notification_id)
            if notification is None:
                continue
            if deliver_notification(notification):
                sent += 1
            else:
                failed += 1

        self.stdout.write(f'Отправлено: {sent}; отложено для повтора: {failed}.')
