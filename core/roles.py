MASTER_GROUP = 'masters'
DISPATCHER_GROUP = 'dispatchers'


def validate_master_assignment(service_request, new_master, reason=''):
    from django.core.exceptions import ValidationError
    from .models import ServiceRequest

    if new_master is not None and not is_master(new_master):
        raise ValidationError({'assigned_to': 'Назначить можно только активного пользователя с ролью мастера.'})

    old_master_id = service_request.assigned_to_id
    new_master_id = getattr(new_master, 'pk', None)
    if old_master_id == new_master_id:
        return
    if service_request.work_started_at or service_request.completion_status != ServiceRequest.CompletionStatus.NONE:
        raise ValidationError({'assigned_to': 'Нельзя менять мастера после начала работы или отправки отчёта.'})
    if old_master_id and not reason.strip():
        raise ValidationError({'reassignment_reason': 'Укажите причину переназначения мастера.'})


def is_master(user):
    return bool(
        user
        and user.is_authenticated
        and user.is_active
        and user.groups.filter(name=MASTER_GROUP).exists()
    )


def is_dispatcher(user):
    return bool(
        user
        and user.is_authenticated
        and user.is_active
        and (user.is_superuser or user.groups.filter(name=DISPATCHER_GROUP).exists())
    )


def ensure_operational_roles(**kwargs):
    from django.contrib.auth.models import Group, Permission
    from django.contrib.contenttypes.models import ContentType
    from .models import ClientNotification, CompletionMedia, ExtraWork, ServiceRequest, ServiceRequestEvent

    Group.objects.get_or_create(name=MASTER_GROUP)
    dispatchers, _ = Group.objects.get_or_create(name=DISPATCHER_GROUP)
    permissions = []
    grants = (
        (ServiceRequest, ('view', 'change')),
        (ServiceRequestEvent, ('view',)),
        (ExtraWork, ('view',)),
        (CompletionMedia, ('view',)),
        (ClientNotification, ('view',)),
    )
    for model, actions in grants:
        content_type = ContentType.objects.get_for_model(model)
        for action in actions:
            codename = f'{action}_{model._meta.model_name}'
            permission, _ = Permission.objects.get_or_create(
                content_type=content_type,
                codename=codename,
                defaults={'name': f'Can {action} {model._meta.verbose_name}'},
            )
            permissions.append(permission)
    dispatchers.permissions.add(*permissions)
