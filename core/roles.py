MASTER_GROUP = 'masters'
DISPATCHER_GROUP = 'dispatchers'


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
