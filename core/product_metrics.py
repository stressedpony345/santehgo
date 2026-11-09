from django.db.models import F
from django.utils import timezone

from .models import ProductMetric


def record_product_metric(event):
    metric, _ = ProductMetric.objects.get_or_create(day=timezone.localdate(), event=event)
    ProductMetric.objects.filter(pk=metric.pk).update(count=F('count') + 1)
