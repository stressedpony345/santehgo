import json
import re
import urllib.error
import urllib.request
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import ClientNotification, ServiceRequest


EVENT_TEXT = {
    'created': 'Заявка {number} принята.',
    'assigned': 'По заявке {number} назначен мастер.',
    'started': 'Мастер начал работу по заявке {number}.',
    'completed': 'Работа по заявке {number} завершена.',
    'cancel_requested': 'Запрос на отмену заявки {number} принят.',
}


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _open_provider_request(request, timeout):
    return urllib.request.build_opener(_NoRedirectHandler()).open(request, timeout=timeout)


def normalize_phone(value):
    digits = re.sub(r'\D', '', value or '')
    if len(digits) == 11 and digits.startswith('8'):
        digits = '7' + digits[1:]
    elif len(digits) == 10:
        digits = '7' + digits
    return f'+{digits}'


def enqueue_client_notification(request_id, event, dedupe_key):
    if not settings.CLIENT_NOTIFICATIONS_ENABLED:
        return None
    if event not in ClientNotification.Event.values:
        raise ValueError('Unsupported client notification event')
    service_request = ServiceRequest.objects.get(pk=request_id)
    notification, _ = ClientNotification.objects.get_or_create(
        dedupe_key=dedupe_key,
        defaults={
            'service_request': service_request,
            'event': event,
            'destination': normalize_phone(service_request.phone),
        },
    )
    return notification


def render_notification(notification):
    service_request = notification.service_request
    intro = EVENT_TEXT[notification.event].format(number=service_request.public_number)
    status_url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/request/{service_request.public_token}/"
    return f'{intro} Статус: {status_url}'


def _record_failure(notification, error_label, retryable):
    if not retryable or notification.attempts >= 8:
        notification.status = ClientNotification.Status.DEAD
    else:
        notification.status = ClientNotification.Status.FAILED
        delay_minutes = min(60, 2 ** min(notification.attempts, 5))
        notification.next_attempt_at = timezone.now() + timedelta(minutes=delay_minutes)
    notification.last_error = error_label
    notification.save(update_fields=('attempts', 'status', 'last_error', 'next_attempt_at', 'updated_at'))
    return False


def deliver_notification(notification):
    payload = json.dumps({
        'channel': notification.channel,
        'destination': notification.destination,
        'message': render_notification(notification),
        'idempotency_key': notification.dedupe_key,
    }, ensure_ascii=False).encode('utf-8')
    request = urllib.request.Request(
        settings.CLIENT_NOTIFICATION_WEBHOOK_URL,
        data=payload,
        headers={
            'Authorization': f'Bearer {settings.CLIENT_NOTIFICATION_TOKEN}',
            'Content-Type': 'application/json',
            'Idempotency-Key': notification.dedupe_key,
        },
        method='POST',
    )
    notification.attempts += 1
    try:
        with _open_provider_request(request, settings.CLIENT_NOTIFICATION_TIMEOUT) as response:
            if not 200 <= response.status < 300:
                raise urllib.error.HTTPError(request.full_url, response.status, 'provider error', response.headers, None)
            response.read(4096)
    except urllib.error.HTTPError as error:
        retryable = error.code in (408, 429) or error.code >= 500
        return _record_failure(notification, f'HTTP {error.code}', retryable)
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        return _record_failure(notification, type(error).__name__, True)

    notification.status = ClientNotification.Status.SENT
    notification.sent_at = timezone.now()
    notification.last_error = ''
    notification.save(update_fields=('attempts', 'status', 'sent_at', 'last_error', 'updated_at'))
    return True
