from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.test import RequestFactory

from core.models import ServiceRequest


class Command(BaseCommand):
    help = 'Render the service request admin list against the current database.'

    def handle(self, *args, **options):
        moderator = get_user_model().objects.filter(is_active=True, is_superuser=True).first()
        if moderator is None:
            raise CommandError('No active superuser is available for the admin smoke test.')
        request = RequestFactory().get('/admin/core/servicerequest/')
        request.user = moderator
        request.current_app = admin.site.name
        response = admin.site._registry[ServiceRequest].changelist_view(request)
        response.render()
        if response.status_code != 200:
            raise CommandError(f'Service request admin returned HTTP {response.status_code}.')
        self.stdout.write(self.style.SUCCESS('Service request admin rendered successfully.'))
