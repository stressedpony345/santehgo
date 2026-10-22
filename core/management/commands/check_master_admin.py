from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.test import RequestFactory
from unittest.mock import patch

from core.models import ServiceRequest


class Command(BaseCommand):
    help = 'Render the service request admin list against the current database.'

    def add_arguments(self, parser):
        parser.add_argument('--check-approval', action='store_true')

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
        if options['check_approval']:
            pending_id = ServiceRequest.objects.filter(
                completion_status=ServiceRequest.CompletionStatus.PENDING,
            ).values_list('pk', flat=True).first()
            if pending_id is None:
                self.stdout.write('No pending request to check approval.')
                return
            action_request = RequestFactory().post('/admin/core/servicerequest/')
            action_request.user = moderator
            model_admin = admin.site._registry[ServiceRequest]
            with transaction.atomic():
                with patch.object(model_admin, 'message_user'):
                    model_admin.approve_completion(
                        action_request,
                        ServiceRequest.objects.select_related('assigned_to').filter(pk=pending_id),
                    )
                item = ServiceRequest.objects.get(pk=pending_id)
                if item.completion_status != ServiceRequest.CompletionStatus.APPROVED:
                    raise CommandError('Admin approval did not update the pending request.')
                transaction.set_rollback(True)
            self.stdout.write(self.style.SUCCESS('Admin approval passed; transaction rolled back.'))
