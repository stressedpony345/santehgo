from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = 'core'

    def ready(self):
        from . import checks  # noqa: F401
        from django.db.models.signals import post_migrate
        from .roles import ensure_operational_roles

        post_migrate.connect(ensure_operational_roles, sender=self, dispatch_uid='core.ensure_operational_roles')
