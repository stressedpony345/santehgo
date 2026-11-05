from .models import ServiceRequestEvent


def record_request_event(service_request, event, actor=None, *, from_state='', to_state='', metadata=None):
    return ServiceRequestEvent.objects.create(
        service_request=service_request,
        event=event,
        actor=actor if getattr(actor, 'is_authenticated', False) else None,
        from_state=from_state,
        to_state=to_state,
        metadata=metadata or {},
    )
