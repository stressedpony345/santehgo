import json
import logging
import urllib.error
import urllib.request

from django.conf import settings


def send_error_alert(message, context=None):
    if not settings.ERROR_ALERTS_ENABLED:
        return False
    payload = json.dumps({
        'service': 'santehgo',
        'site': settings.PUBLIC_BASE_URL,
        'message': str(message)[:500],
        'context': context or {},
    }, ensure_ascii=False).encode('utf-8')
    request = urllib.request.Request(
        settings.ERROR_ALERT_WEBHOOK_URL,
        data=payload,
        headers={
            'Authorization': f'Bearer {settings.ERROR_ALERT_TOKEN}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.ERROR_ALERT_TIMEOUT):
            return True
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


class ErrorAlertHandler(logging.Handler):
    def emit(self, record):
        try:
            send_error_alert(
                self.format(record),
                {'logger': record.name, 'level': record.levelname},
            )
        except Exception:
            self.handleError(record)
