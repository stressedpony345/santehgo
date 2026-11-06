import hashlib
import hmac
from datetime import datetime, timezone as datetime_timezone

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import PublicRequestRateBucket


def consume_public_request_attempt(request):
    limit = max(1, int(settings.PUBLIC_REQUEST_RATE_LIMIT))
    window_seconds = max(1, int(settings.PUBLIC_REQUEST_RATE_WINDOW_SECONDS))
    source = request.META.get(settings.PUBLIC_CLIENT_IP_HEADER, '') or request.META.get('REMOTE_ADDR', '')
    fingerprint = hmac.new(
        settings.SECRET_KEY.encode(),
        source.encode(),
        hashlib.sha256,
    ).hexdigest()
    now = timezone.now()
    bucket_timestamp = int(now.timestamp()) // window_seconds * window_seconds
    window_started_at = datetime.fromtimestamp(bucket_timestamp, tz=datetime_timezone.utc)

    with transaction.atomic():
        bucket, _ = PublicRequestRateBucket.objects.get_or_create(
            fingerprint=fingerprint,
            window_started_at=window_started_at,
        )
        consumed = PublicRequestRateBucket.objects.filter(pk=bucket.pk, attempts__lt=limit).update(
            attempts=F('attempts') + 1,
        )

    return consumed == 1, window_seconds
