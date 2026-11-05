import json
import urllib.error
from io import BytesIO
from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core import signing
from django.core.management import call_command
from django.test import TestCase
from django.test import override_settings
from django.utils import timezone
from PIL import Image

from .models import Category, ClientNotification, ServiceRequest, SubCategory, WithdrawalRequest, Work


class MultiServiceRequestTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name='Тест', slug='test')
        self.first = SubCategory.objects.create(
            category=category,
            name='Первая работа',
            approximate_price=1000,
        )
        self.second = SubCategory.objects.create(
            category=category,
            name='Вторая работа',
            approximate_price=2000,
        )
        self.first_work = Work.objects.create(
            service=self.first,
            name='Первая конкретная работа',
            price=500,
        )
        self.second_work = Work.objects.create(
            service=self.second,
            name='Вторая конкретная работа',
            price=800,
        )

    def test_catalog_contains_work_list_controls(self):
        response = self.client.get('/')
        self.assertContains(response, 'Ваш список работ')
        self.assertContains(response, 'Оставить заявку')
        self.assertContains(response, 'work-list-submit')
        self.assertContains(response, '/personal-data-consent/')

    @override_settings(
        LEGAL_OPERATOR_NAME='ИП Иванов Иван Иванович',
        LEGAL_OPERATOR_TAX_ID='745300000000',
        LEGAL_OPERATOR_ADDRESS='г. Челябинск, ул. Тестовая, 1',
        LEGAL_CONTACT_EMAIL='privacy@example.test',
        PERSONAL_DATA_CONSENT_VERSION='2026-11-05',
    )
    def test_personal_data_consent_page_is_versioned_and_names_the_operator(self):
        response = self.client.get('/personal-data-consent/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ИП Иванов Иван Иванович')
        self.assertContains(response, '745300000000')
        self.assertContains(response, 'privacy@example.test')
        self.assertContains(response, 'Версия 2026-11-05')

    @override_settings(LEGAL_OPERATOR_NAME='')
    def test_personal_data_consent_page_does_not_publish_without_operator_identity(self):
        response = self.client.get('/personal-data-consent/')

        self.assertEqual(response.status_code, 503)

    @override_settings(
        LEGAL_PAGES_REQUIRED=True,
        LEGAL_OPERATOR_NAME='',
        PERSONAL_DATA_CONSENT_VERSION='',
        PERSONAL_DATA_CONSENT_EFFECTIVE_DATE='',
    )
    def test_required_legal_configuration_reports_deploy_errors(self):
        from .checks import check_legal_configuration

        errors = check_legal_configuration(None)

        self.assertEqual({error.id for error in errors}, {'core.E001', 'core.E002', 'core.E003'})

    def test_request_accepts_multiple_services(self):
        response = self.client.post(
            '/api/requests/',
            data=json.dumps({
                'full_name': 'Тестовый клиент',
                'phone': '+7 999 123-45-67',
                'consent': True,
                'subcategory_ids': [self.first.id, self.second.id],
            }),
            content_type='application/json',
            HTTP_IDEMPOTENCY_KEY='multi-service-request-1',
        )

        self.assertEqual(response.status_code, 200)
        self.assertRegex(response.json()['success_url'], r'^/request/[0-9a-f-]+/$')
        request = ServiceRequest.objects.get()
        self.assertEqual(request.subcategories.count(), 2)
        self.assertIsNotNone(request.consented_at)
        self.assertEqual(request.consent_version, '2026-11-05')

    @patch('core.views.threading.Thread')
    def test_repeated_idempotency_key_returns_the_same_public_request(self, thread):
        payload = json.dumps({
            'full_name': 'Повторный клиент',
            'phone': '+7 999 123-45-67',
            'consent': True,
            'subcategory_ids': [self.first.id],
        })
        headers = {'HTTP_IDEMPOTENCY_KEY': '8b3fbdb4-7399-47e3-aa6a-4bd04fa6bf78'}

        with self.captureOnCommitCallbacks(execute=True):
            first = self.client.post('/api/requests/', data=payload, content_type='application/json', **headers)
            repeated = self.client.post('/api/requests/', data=payload, content_type='application/json', **headers)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(ServiceRequest.objects.count(), 1)
        self.assertEqual(first.json()['request_number'], repeated.json()['request_number'])
        self.assertEqual(first.json()['success_url'], repeated.json()['success_url'])
        self.assertRegex(first.json()['request_number'], r'^SG-\d{6}$')
        self.assertIn('/request/', first.json()['success_url'])
        thread.assert_called_once()

    def test_idempotency_key_rejects_a_different_payload(self):
        headers = {'HTTP_IDEMPOTENCY_KEY': 'f9fc0bd0-2d3c-48e3-9023-9fccf2e32b27'}
        original = {
            'full_name': 'Первый клиент',
            'phone': '+7 999 123-45-67',
            'consent': True,
            'subcategory_ids': [self.first.id],
        }
        changed = {**original, 'phone': '+7 999 765-43-21'}

        first = self.client.post('/api/requests/', data=json.dumps(original), content_type='application/json', **headers)
        repeated = self.client.post('/api/requests/', data=json.dumps(changed), content_type='application/json', **headers)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(repeated.status_code, 409)
        self.assertEqual(ServiceRequest.objects.count(), 1)

    def test_idempotency_hash_uses_the_selected_set_not_input_order(self):
        headers = {'HTTP_IDEMPOTENCY_KEY': 'canonical-selection-key'}
        original = {
            'full_name': 'Клиент', 'phone': '+7 999 123-45-67', 'consent': True,
            'work_ids': [self.first_work.id, self.second_work.id],
        }
        reordered = {**original, 'work_ids': [self.second_work.id, self.first_work.id, self.first_work.id]}

        first = self.client.post('/api/requests/', data=json.dumps(original), content_type='application/json', **headers)
        repeated = self.client.post('/api/requests/', data=json.dumps(reordered), content_type='application/json', **headers)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(ServiceRequest.objects.count(), 1)

    def test_request_accepts_works_from_different_services(self):
        response = self.client.post(
            '/api/requests/',
            data=json.dumps({
                'full_name': 'Тестовый клиент',
                'phone': '+7 999 123-45-67',
                'consent': True,
                'work_ids': [self.first_work.id, self.second_work.id],
            }),
            content_type='application/json',
            HTTP_IDEMPOTENCY_KEY='multi-work-request-1',
        )

        self.assertEqual(response.status_code, 200)
        request = ServiceRequest.objects.get()
        self.assertEqual(request.works.count(), 2)
        self.assertEqual(request.subcategories.count(), 2)

    def test_request_requires_explicit_data_processing_consent(self):
        for consent in (None, False, 'true'):
            with self.subTest(consent=consent):
                payload = {
                    'full_name': 'Клиент без согласия',
                    'phone': '+7 999 123-45-67',
                    'subcategory_ids': [self.first.id],
                }
                if consent is not None:
                    payload['consent'] = consent
                response = self.client.post(
                    '/api/requests/',
                    data=json.dumps(payload),
                    content_type='application/json',
                )

                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()['field'], 'consent')
        self.assertEqual(ServiceRequest.objects.count(), 0)

    def test_request_requires_idempotency_key(self):
        response = self.client.post(
            '/api/requests/',
            data=json.dumps({
                'full_name': 'Клиент без ключа',
                'phone': '+7 999 123-45-67',
                'consent': True,
                'subcategory_ids': [self.first.id],
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(ServiceRequest.objects.count(), 0)

    def test_request_success_page(self):
        response = self.client.get('/request-success/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Заявка принята')
        self.assertContains(response, 'Вернуться на главную')

    def test_public_request_page_shows_number_summary_and_next_step(self):
        request = ServiceRequest.objects.create(
            full_name='Иван',
            phone='+7 999 123-45-67',
            address='ул. Тестовая, 10',
            preferred_time='Сегодня, 12:00–15:00',
        )
        request.subcategories.add(self.first)

        response = self.client.get(f'/request/{request.public_token}/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, request.public_number)
        self.assertContains(response, 'ул. Тестовая, 10')
        self.assertContains(response, self.first.name)
        self.assertContains(response, 'Ожидает мастера')
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertEqual(response['Referrer-Policy'], 'no-referrer')
        self.assertEqual(response['X-Robots-Tag'], 'noindex, nofollow')

    def test_public_request_page_maps_internal_states_to_client_language(self):
        states = (
            ({'assigned_to': get_user_model().objects.create_user(username='status-master')}, 'Мастер назначен'),
            ({'work_started_at': timezone.now()}, 'Мастер выполняет работу'),
            ({'completion_status': ServiceRequest.CompletionStatus.PENDING}, 'Проверяем результат'),
            ({'completion_status': ServiceRequest.CompletionStatus.REJECTED}, 'Мастер уточняет результат'),
            ({'completion_status': ServiceRequest.CompletionStatus.APPROVED}, 'Работа завершена'),
            ({'completion_status': ServiceRequest.CompletionStatus.APPROVED, 'cancel_requested_at': timezone.now()}, 'Запрос на отмену принят'),
        )
        for index, (state, expected) in enumerate(states):
            with self.subTest(expected=expected):
                request = ServiceRequest.objects.create(phone=f'+790000001{index:02d}', **state)
                self.assertContains(self.client.get(f'/request/{request.public_token}/'), expected)

    def test_unknown_public_request_token_returns_404(self):
        response = self.client.get('/request/00000000-0000-0000-0000-000000000000/')

        self.assertEqual(response.status_code, 404)

    def test_client_can_request_callback_or_cancel_before_work_starts(self):
        request = ServiceRequest.objects.create(phone='+7 999 123-45-67')

        callback = self.client.post(f'/request/{request.public_token}/callback/', HTTP_ACCEPT='application/json')
        cancel = self.client.post(f'/request/{request.public_token}/cancel/', HTTP_ACCEPT='application/json')

        self.assertEqual(callback.status_code, 200)
        self.assertEqual(cancel.status_code, 200)
        request.refresh_from_db()
        self.assertIsNotNone(request.callback_requested_at)
        self.assertIsNotNone(request.cancel_requested_at)

    def test_client_cannot_cancel_after_work_starts(self):
        request = ServiceRequest.objects.create(phone='+7 999 123-45-67', work_started_at=timezone.now())

        response = self.client.post(f'/request/{request.public_token}/cancel/', HTTP_ACCEPT='application/json')

        self.assertEqual(response.status_code, 409)
        request.refresh_from_db()
        self.assertIsNone(request.cancel_requested_at)

    def test_client_cannot_request_callback_after_work_starts(self):
        request = ServiceRequest.objects.create(phone='+7 999 123-45-67', work_started_at=timezone.now())

        response = self.client.post(
            f'/request/{request.public_token}/callback/',
            HTTP_ACCEPT='application/json',
        )

        self.assertEqual(response.status_code, 409)
        request.refresh_from_db()
        self.assertIsNone(request.callback_requested_at)

    def test_public_actions_are_hidden_and_rejected_after_request_leaves_queue(self):
        states = (
            {'cancel_requested_at': timezone.now()},
            {'completion_status': ServiceRequest.CompletionStatus.PENDING},
            {'completion_status': ServiceRequest.CompletionStatus.REJECTED},
            {'completion_status': ServiceRequest.CompletionStatus.APPROVED},
        )
        for index, state in enumerate(states):
            with self.subTest(state=state):
                request = ServiceRequest.objects.create(phone=f'+7 999 123-45-{index:02d}', **state)
                page = self.client.get(f'/request/{request.public_token}/')
                callback = self.client.post(
                    f'/request/{request.public_token}/callback/', HTTP_ACCEPT='application/json'
                )
                cancel = self.client.post(
                    f'/request/{request.public_token}/cancel/', HTTP_ACCEPT='application/json'
                )

                self.assertNotContains(page, f'/request/{request.public_token}/callback/')
                self.assertNotContains(page, f'/request/{request.public_token}/cancel/')
                self.assertEqual(callback.status_code, 409)
                self.assertEqual(cancel.status_code, 409)

    def test_html_callback_action_returns_to_status_with_feedback(self):
        request = ServiceRequest.objects.create(phone='+7 999 123-45-67')

        response = self.client.post(f'/request/{request.public_token}/callback/')

        self.assertRedirects(response, f'/request/{request.public_token}/?action=callback')

    def test_stale_html_action_returns_to_status_with_explanation(self):
        request = ServiceRequest.objects.create(phone='+7 999 123-45-67', work_started_at=timezone.now())

        response = self.client.post(f'/request/{request.public_token}/cancel/', follow=True)

        self.assertRedirects(response, f'/request/{request.public_token}/?action=unavailable')
        self.assertContains(response, 'уже в работе или закрыта')


class ClientNotificationTests(TestCase):
    @override_settings(CLIENT_NOTIFICATIONS_ENABLED=True)
    @patch('core.management.commands.send_client_notifications.deliver_notification', return_value=True)
    def test_worker_does_not_reclaim_a_fresh_sending_notification(self, deliver):
        service_request = ServiceRequest.objects.create(phone='+7 999 123-45-67')
        notification = ClientNotification.objects.create(
            service_request=service_request,
            event=ClientNotification.Event.CREATED,
            dedupe_key=f'request:{service_request.pk}:created',
            destination='+79991234567',
            status=ClientNotification.Status.SENDING,
            next_attempt_at=timezone.now() + timedelta(minutes=5),
        )

        call_command('send_client_notifications', limit=10)

        deliver.assert_not_called()
        notification.refresh_from_db()
        self.assertEqual(notification.status, ClientNotification.Status.SENDING)

    @override_settings(CLIENT_NOTIFICATIONS_ENABLED=True)
    @patch('core.management.commands.send_client_notifications.deliver_notification', return_value=True)
    def test_worker_reclaims_a_stale_sending_notification_once(self, deliver):
        service_request = ServiceRequest.objects.create(phone='+7 999 123-45-67')
        notification = ClientNotification.objects.create(
            service_request=service_request,
            event=ClientNotification.Event.CREATED,
            dedupe_key=f'request:{service_request.pk}:created',
            destination='+79991234567',
            status=ClientNotification.Status.SENDING,
            next_attempt_at=timezone.now() - timedelta(seconds=1),
        )

        call_command('send_client_notifications', limit=10)

        deliver.assert_called_once()

    @override_settings(CLIENT_NOTIFICATIONS_ENABLED=True)
    def test_notification_lease_can_only_be_claimed_once(self):
        from core.management.commands.send_client_notifications import claim_notification

        service_request = ServiceRequest.objects.create(phone='+7 999 123-45-67')
        notification = ClientNotification.objects.create(
            service_request=service_request,
            event=ClientNotification.Event.CREATED,
            dedupe_key=f'request:{service_request.pk}:created',
            destination='+79991234567',
            next_attempt_at=timezone.now() - timedelta(seconds=1),
        )
        claim_time = timezone.now()

        self.assertIsNotNone(claim_notification(notification.pk, claim_time))
        self.assertIsNone(claim_notification(notification.pk, claim_time))

    @override_settings(
        CLIENT_NOTIFICATIONS_ENABLED=True,
        CLIENT_NOTIFICATION_WEBHOOK_URL='',
        CLIENT_NOTIFICATION_TOKEN='',
        PUBLIC_BASE_URL='',
    )
    def test_enabled_notifications_require_complete_production_configuration(self):
        from .checks import check_client_notification_configuration

        errors = check_client_notification_configuration(None)

        self.assertEqual({error.id for error in errors}, {'core.E010', 'core.E011', 'core.E012'})

    @override_settings(
        CLIENT_NOTIFICATIONS_ENABLED=True,
        CLIENT_NOTIFICATION_WEBHOOK_URL='https://user:password@127.0.0.1/send',
        CLIENT_NOTIFICATION_TOKEN='token',
        PUBLIC_BASE_URL='https:///missing-host',
    )
    def test_notification_urls_must_be_public_https_hosts_without_credentials(self):
        from .checks import check_client_notification_configuration

        errors = check_client_notification_configuration(None)

        self.assertEqual({error.id for error in errors}, {'core.E010', 'core.E012'})

    @override_settings(CLIENT_NOTIFICATIONS_ENABLED=True)
    def test_enqueue_is_idempotent_for_the_same_request_event(self):
        from .notifications import enqueue_client_notification

        service_request = ServiceRequest.objects.create(phone='+7 999 123-45-67')
        first = enqueue_client_notification(service_request.pk, 'created', f'request:{service_request.pk}:created')
        repeated = enqueue_client_notification(service_request.pk, 'created', f'request:{service_request.pk}:created')

        self.assertEqual(first.pk, repeated.pk)
        self.assertEqual(ClientNotification.objects.count(), 1)
        self.assertEqual(first.destination, '+79991234567')

    @override_settings(CLIENT_NOTIFICATIONS_ENABLED=True)
    @patch('core.views.threading.Thread')
    def test_new_request_enqueues_created_notification_after_commit(self, thread):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                '/api/requests/',
                data=json.dumps({
                    'full_name': 'Клиент', 'phone': '+7 999 123-45-67',
                    'issue': 'Нужен сантехник', 'consent': True,
                }),
                content_type='application/json',
                HTTP_IDEMPOTENCY_KEY='notification-create-key',
            )

        self.assertEqual(response.status_code, 200)
        notification = ClientNotification.objects.get()
        self.assertEqual(notification.event, 'created')
        self.assertEqual(notification.dedupe_key, f'request:{notification.service_request_id}:created')

    @override_settings(CLIENT_NOTIFICATIONS_ENABLED=True)
    def test_successful_transitions_enqueue_each_event_once(self):
        master = get_user_model().objects.create_user(username='notify-master', password='pass', is_staff=True)
        master.groups.add(Group.objects.get_or_create(name='masters')[0])
        moderator = get_user_model().objects.create_superuser(username='notify-admin', password='pass')
        assigned_request = ServiceRequest.objects.create(phone='+7 999 123-45-67')
        cancelled_request = ServiceRequest.objects.create(phone='+7 999 123-45-68')

        self.client.force_login(master)
        self.assertEqual(self.client.post(f'/masters/api/requests/{assigned_request.pk}/claim/').status_code, 200)
        self.assertEqual(self.client.post(f'/masters/api/requests/{assigned_request.pk}/claim/').status_code, 409)
        self.assertEqual(self.client.post(f'/masters/api/requests/{assigned_request.pk}/start/').status_code, 200)
        self.assertEqual(self.client.post(f'/masters/api/requests/{assigned_request.pk}/start/').status_code, 409)

        self.client.logout()
        self.assertEqual(
            self.client.post(
                f'/request/{cancelled_request.public_token}/cancel/', HTTP_ACCEPT='application/json'
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                f'/request/{cancelled_request.public_token}/cancel/', HTTP_ACCEPT='application/json'
            ).status_code,
            409,
        )

        assigned_request.completion_status = ServiceRequest.CompletionStatus.PENDING
        assigned_request.save(update_fields=('completion_status',))
        self.client.force_login(moderator)
        self.client.post('/admin/core/servicerequest/', {
            'action': 'approve_completion', '_selected_action': [assigned_request.pk], 'index': '0',
        })

        events = list(ClientNotification.objects.order_by('event').values_list('event', flat=True))
        self.assertEqual(events, ['assigned', 'cancel_requested', 'completed', 'started'])

    @override_settings(CLIENT_NOTIFICATIONS_ENABLED=True)
    @patch('core.views.enqueue_client_notification', side_effect=RuntimeError('outbox unavailable'))
    def test_request_and_outbox_roll_back_together(self, enqueue):
        with self.assertRaises(RuntimeError):
            self.client.post(
                '/api/requests/',
                data=json.dumps({
                    'phone': '+7 999 123-45-67', 'issue': 'Нужен сантехник', 'consent': True,
                }),
                content_type='application/json',
                HTTP_IDEMPOTENCY_KEY='atomic-outbox-key',
            )

        self.assertEqual(ServiceRequest.objects.count(), 0)
        self.assertEqual(ClientNotification.objects.count(), 0)

    @override_settings(
        CLIENT_NOTIFICATIONS_ENABLED=True,
        CLIENT_NOTIFICATION_WEBHOOK_URL='https://sms.example.test/send',
        CLIENT_NOTIFICATION_TOKEN='secret-token',
        PUBLIC_BASE_URL='https://example.test',
    )
    @patch('core.notifications._open_provider_request')
    def test_delivery_contains_status_link_but_not_private_request_details(self, open_provider):
        from .notifications import deliver_notification, enqueue_client_notification

        response = open_provider.return_value.__enter__.return_value
        response.status = 200
        response.read.return_value = b'{}'
        service_request = ServiceRequest.objects.create(
            full_name='Секретное имя', phone='+7 999 123-45-67',
            address='Секретный адрес', issue='Секретная проблема',
        )
        notification = enqueue_client_notification(
            service_request.pk, 'created', f'request:{service_request.pk}:created'
        )

        self.assertTrue(deliver_notification(notification))
        sent_payload = json.loads(open_provider.call_args.args[0].data.decode('utf-8'))
        self.assertIn(service_request.public_number, sent_payload['message'])
        self.assertIn(f'https://example.test/request/{service_request.public_token}/', sent_payload['message'])
        self.assertNotIn('Секретное имя', sent_payload['message'])
        self.assertNotIn('Секретный адрес', sent_payload['message'])
        self.assertNotIn('Секретная проблема', sent_payload['message'])

    @override_settings(
        CLIENT_NOTIFICATIONS_ENABLED=True,
        CLIENT_NOTIFICATION_WEBHOOK_URL='https://sms.example.test/send',
        CLIENT_NOTIFICATION_TOKEN='secret-token',
        PUBLIC_BASE_URL='https://example.test',
    )
    @patch('core.notifications._open_provider_request', side_effect=urllib.error.URLError('secret provider detail'))
    def test_provider_failure_is_retryable_without_storing_secret_details(self, open_provider):
        from .notifications import deliver_notification, enqueue_client_notification

        service_request = ServiceRequest.objects.create(phone='+7 999 123-45-67')
        notification = enqueue_client_notification(
            service_request.pk, 'created', f'request:{service_request.pk}:created'
        )

        self.assertFalse(deliver_notification(notification))
        notification.refresh_from_db()
        self.assertEqual(notification.status, ClientNotification.Status.FAILED)
        self.assertEqual(notification.attempts, 1)
        self.assertEqual(notification.last_error, 'URLError')
        self.assertGreater(notification.next_attempt_at, timezone.now())

    @override_settings(
        CLIENT_NOTIFICATIONS_ENABLED=True,
        CLIENT_NOTIFICATION_WEBHOOK_URL='https://sms.example.test/send',
        CLIENT_NOTIFICATION_TOKEN='secret-token',
        PUBLIC_BASE_URL='https://example.test',
    )
    @patch('core.notifications._open_provider_request', side_effect=TimeoutError())
    def test_repeated_transient_failure_eventually_moves_to_dead_letter(self, open_provider):
        from .notifications import deliver_notification, enqueue_client_notification

        service_request = ServiceRequest.objects.create(phone='+7 999 123-45-67')
        notification = enqueue_client_notification(
            service_request.pk, 'created', f'request:{service_request.pk}:created'
        )
        notification.attempts = 7
        notification.save(update_fields=('attempts',))

        self.assertFalse(deliver_notification(notification))
        notification.refresh_from_db()
        self.assertEqual(notification.status, ClientNotification.Status.DEAD)
        self.assertEqual(notification.attempts, 8)

    @override_settings(
        CLIENT_NOTIFICATIONS_ENABLED=True,
        CLIENT_NOTIFICATION_WEBHOOK_URL='https://sms.example.test/send',
        CLIENT_NOTIFICATION_TOKEN='secret-token',
        PUBLIC_BASE_URL='https://example.test',
    )
    @patch('core.notifications._open_provider_request')
    def test_permanent_provider_rejection_moves_notification_to_dead_letter(self, open_provider):
        from .notifications import deliver_notification, enqueue_client_notification

        open_provider.side_effect = urllib.error.HTTPError(
            'https://sms.example.test/send', 400, 'bad destination', {}, None
        )
        service_request = ServiceRequest.objects.create(phone='+7 999 123-45-67')
        notification = enqueue_client_notification(
            service_request.pk, 'created', f'request:{service_request.pk}:created'
        )

        self.assertFalse(deliver_notification(notification))
        notification.refresh_from_db()
        self.assertEqual(notification.status, ClientNotification.Status.DEAD)
        self.assertEqual(notification.last_error, 'HTTP 400')


class MasterAppTests(TestCase):
    def setUp(self):
        self.master = get_user_model().objects.create_user(
            username='master-test',
            password='Strong-test-pass-2026',
            is_staff=True,
        )
        self.master.groups.add(Group.objects.get_or_create(name='masters')[0])
        category = Category.objects.create(name='Сантехника', slug='master-test')
        service = SubCategory.objects.create(category=category, name='Ремонт', approximate_price=1500)
        self.work = Work.objects.create(service=service, name='Замена крана', price=2300)
        self.request_item = ServiceRequest.objects.create(phone='+79000000000', issue='Течёт кран')
        self.request_item.subcategories.add(service)
        self.request_item.works.add(self.work)

    def test_staff_without_master_role_cannot_open_master_api(self):
        dispatcher = get_user_model().objects.create_user(
            username='dispatcher-only', password='pass', is_staff=True,
        )
        dispatcher.groups.add(Group.objects.get_or_create(name='dispatchers')[0])
        self.client.force_login(dispatcher)

        response = self.client.get('/masters/api/requests/')

        self.assertEqual(response.status_code, 302)
        self.assertIn('/masters/login/', response.url)

    def test_master_pages_require_login(self):
        response = self.client.get('/masters/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/masters/login/', response.url)

    def test_master_can_claim_request(self):
        self.client.force_login(self.master)
        queue = self.client.get('/masters/api/requests/').json()
        self.assertEqual(queue['available'][0]['price'], 2300)
        self.assertNotIn('phone', queue['available'][0])
        self.assertNotIn('full_name', queue['available'][0])
        self.assertNotIn('address', queue['available'][0])

        response = self.client.post(f'/masters/api/requests/{self.request_item.id}/claim/')
        self.assertEqual(response.status_code, 200)
        self.request_item.refresh_from_db()
        self.assertEqual(self.request_item.assigned_to, self.master)
        mine = self.client.get('/masters/api/requests/').json()['mine'][0]
        self.assertEqual(mine['phone'], self.request_item.phone)
        self.assertIsNone(self.request_item.work_started_at)
        self.assertEqual(self.client.get('/masters/api/requests/').json()['mine'][0]['work_started_at'], '')
        self.assertEqual(self.client.post(f'/masters/api/requests/{self.request_item.id}/claim/').status_code, 409)
        self.assertEqual(self.client.post(f'/masters/api/requests/{self.request_item.id}/start/').status_code, 200)
        self.assertEqual(self.client.post(f'/masters/api/requests/{self.request_item.id}/start/').status_code, 409)
        self.request_item.refresh_from_db()
        self.assertIsNotNone(self.request_item.work_started_at)

    def test_master_cannot_claim_or_start_cancelled_request(self):
        self.request_item.cancel_requested_at = timezone.now()
        self.request_item.save(update_fields=('cancel_requested_at',))
        self.client.force_login(self.master)

        queue = self.client.get('/masters/api/requests/').json()
        claim = self.client.post(f'/masters/api/requests/{self.request_item.id}/claim/')

        self.assertNotIn(self.request_item.id, [item['id'] for item in queue['available']])
        self.assertEqual(claim.status_code, 409)
        self.request_item.assigned_to = self.master
        self.request_item.save(update_fields=('assigned_to',))
        start = self.client.post(f'/masters/api/requests/{self.request_item.id}/start/')
        self.assertEqual(start.status_code, 409)

    def test_master_cannot_claim_request_that_already_left_the_queue(self):
        self.client.force_login(self.master)
        invalid_states = (
            {'work_started_at': timezone.now()},
            {'completion_status': ServiceRequest.CompletionStatus.PENDING},
            {'completion_status': ServiceRequest.CompletionStatus.REJECTED},
            {'completion_status': ServiceRequest.CompletionStatus.APPROVED},
        )
        for index, state in enumerate(invalid_states):
            item = ServiceRequest.objects.create(phone=f'+790000001{index:02d}', **state)
            with self.subTest(state=state):
                available_ids = [entry['id'] for entry in self.client.get('/masters/api/requests/').json()['available']]
                self.assertNotIn(item.pk, available_ids)
                self.assertEqual(self.client.post(f'/masters/api/requests/{item.pk}/claim/').status_code, 409)

    def test_start_requires_assigned_master(self):
        self.client.force_login(self.master)
        url = f'/masters/api/requests/{self.request_item.id}/start/'
        self.assertEqual(self.client.post(url).status_code, 404)
        self.client.post(f'/masters/api/requests/{self.request_item.id}/claim/')
        other = get_user_model().objects.create_user(username='other-starter', password='pass', is_staff=True)
        other.groups.add(Group.objects.get_or_create(name='masters')[0])
        self.client.force_login(other)
        self.assertEqual(self.client.post(url).status_code, 404)

    def test_manifest_is_available(self):
        response = self.client.get('/masters/manifest.webmanifest')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['start_url'], '/masters/')

    def test_master_adds_catalog_and_custom_work_to_claimed_request(self):
        self.client.force_login(self.master)
        self.client.post(f'/masters/api/requests/{self.request_item.id}/claim/')
        self.assertEqual(self.client.post(f'/masters/api/requests/{self.request_item.id}/extra-works/', json.dumps({'work_id': self.work.id}), content_type='application/json').status_code, 409)
        self.client.post(f'/masters/api/requests/{self.request_item.id}/start/')
        search = self.client.get('/masters/api/works/', {'q': 'Замена'}).json()
        self.assertIn(self.work.id, [item['id'] for item in search['works']])

        catalog = self.client.post(
            f'/masters/api/requests/{self.request_item.id}/extra-works/',
            data=json.dumps({'work_id': self.work.id}), content_type='application/json',
        )
        self.assertEqual(catalog.status_code, 200)
        self.assertEqual(catalog.json()['price'], 4600)
        custom = self.client.post(
            f'/masters/api/requests/{self.request_item.id}/extra-works/',
            data=json.dumps({'name': 'Дополнительный выезд', 'price': 700}), content_type='application/json',
        )
        self.assertEqual(custom.status_code, 200)
        self.assertEqual(custom.json()['price'], 5300)
        self.work.price = 3000
        self.work.save()
        queue = self.client.get('/masters/api/requests/').json()['mine'][0]
        self.assertEqual(queue['price'], 6000)
        self.assertEqual(queue['extra_works'][0]['price'], 2300)
        self.assertEqual(self.request_item.total_price, 6000)

    def test_extra_work_requires_owner_and_active_request(self):
        url = f'/masters/api/requests/{self.request_item.id}/extra-works/'
        body = json.dumps({'name': 'Диагностика', 'price': 500})
        self.client.force_login(self.master)
        self.assertEqual(self.client.post(url, body, content_type='application/json').status_code, 404)
        self.client.post(f'/masters/api/requests/{self.request_item.id}/claim/')
        self.client.post(f'/masters/api/requests/{self.request_item.id}/start/')
        for invalid in ({'name': '', 'price': 500}, {'name': 'Тест', 'price': -1}, {'work_id': 999999}):
            self.assertEqual(self.client.post(url, json.dumps(invalid), content_type='application/json').status_code, 400)
        other = get_user_model().objects.create_user(username='other-master', password='pass', is_staff=True)
        other.groups.add(Group.objects.get_or_create(name='masters')[0])
        self.client.force_login(other)
        self.assertEqual(self.client.post(url, body, content_type='application/json').status_code, 404)
        self.client.force_login(self.master)
        self.request_item.completion_status = ServiceRequest.CompletionStatus.PENDING
        self.request_item.save(update_fields=['completion_status'])
        self.assertEqual(self.client.post(url, body, content_type='application/json').status_code, 409)
        self.assertEqual(self.request_item.extra_works.count(), 0)

    def test_completion_requires_photo_and_waits_for_admin_approval(self):
        self.client.force_login(self.master)
        claim = self.client.post(f'/masters/api/requests/{self.request_item.id}/claim/')
        self.assertEqual(claim.status_code, 200)
        self.assertEqual(self.client.post(f'/masters/api/requests/{self.request_item.id}/start/').status_code, 200)

        missing_photo = self.client.post(f'/masters/api/requests/{self.request_item.id}/complete/')
        self.assertEqual(missing_photo.status_code, 400)

        image = Image.new('RGB', (20, 20), color='white')
        image_bytes = BytesIO()
        image.save(image_bytes, format='JPEG')
        photo = SimpleUploadedFile('work.jpg', image_bytes.getvalue(), content_type='image/jpeg')
        sent = self.client.post(f'/masters/api/requests/{self.request_item.id}/complete/', {'photo': photo})
        self.assertEqual(sent.status_code, 200)
        self.request_item.refresh_from_db()
        self.assertEqual(self.request_item.completion_status, ServiceRequest.CompletionStatus.PENDING)
        self.assertFalse(self.request_item.is_processed)

        queue = self.client.get('/masters/api/requests/').json()
        self.assertEqual(queue['approved_income'], 0)

    def _approve(self):
        moderator, _ = get_user_model().objects.get_or_create(username='moderator', defaults={'is_staff': True, 'is_superuser': True})
        self.client.force_login(moderator)
        response = self.client.post('/admin/core/servicerequest/', {
            'action': 'approve_completion', '_selected_action': [self.request_item.pk], 'index': '0',
        })
        self.assertEqual(response.status_code, 302)
        self.request_item.refresh_from_db()
        self.client.force_login(self.master)
        return moderator

    def test_admin_request_list_and_detail_render(self):
        moderator = get_user_model().objects.create_superuser(username='admin-list', password='pass')
        self.request_item.callback_requested_at = timezone.now()
        self.request_item.cancel_requested_at = timezone.now()
        self.request_item.consented_at = timezone.now()
        self.request_item.consent_version = '2026-11-05'
        self.request_item.save(update_fields=('callback_requested_at', 'cancel_requested_at', 'consented_at', 'consent_version'))
        ServiceRequest.objects.create(phone='+79000000002')
        ServiceRequest.objects.create(phone='+79000000003', completion_status=ServiceRequest.CompletionStatus.APPROVED, is_processed=True)
        pending = ServiceRequest.objects.create(phone='+79000000004', completion_status=ServiceRequest.CompletionStatus.PENDING, assigned_to=self.master)
        self.client.force_login(moderator)
        listing = self.client.get('/admin/core/servicerequest/')
        self.assertEqual(listing.status_code, 200)
        self.assertContains(listing, 'field-client_action')
        self.assertContains(listing, 'Перезвонить')
        self.assertContains(listing, 'Отмена')
        detail = self.client.get(f'/admin/core/servicerequest/{self.request_item.pk}/change/')
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, 'field-callback_requested_at')
        self.assertContains(detail, 'field-consented_at')
        self.assertContains(detail, 'field-consent_version')
        self.assertContains(detail, '2026-11-05')
        call_command('check_master_admin', check_approval=True)
        pending.refresh_from_db()
        self.assertEqual(pending.completion_status, ServiceRequest.CompletionStatus.PENDING)

    def test_admin_approval_does_not_lock_nullable_master_join(self):
        from django.contrib import admin
        from django.test import RequestFactory

        moderator = get_user_model().objects.create_superuser(username='admin-approval', password='pass')
        self.request_item.completion_status = ServiceRequest.CompletionStatus.PENDING
        self.request_item.save(update_fields=['completion_status'])
        request = RequestFactory().post('/admin/core/servicerequest/')
        request.user = moderator
        model_admin = admin.site._registry[ServiceRequest]
        queryset = ServiceRequest.objects.select_related('assigned_to').filter(pk=self.request_item.pk)
        with patch.object(model_admin, 'message_user'):
            model_admin.approve_completion(request, queryset)
        self.request_item.refresh_from_db()
        self.assertEqual(self.request_item.completion_status, ServiceRequest.CompletionStatus.APPROVED)
        self.assertEqual(self.request_item.approved_payout, 920)

    def test_completion_media_approval_and_frozen_40_percent(self):
        self.client.force_login(self.master)
        self.client.post(f'/masters/api/requests/{self.request_item.id}/claim/')
        self.client.post(f'/masters/api/requests/{self.request_item.id}/start/')
        image = Image.new('RGB', (20, 20), color='white')
        content = BytesIO()
        image.save(content, format='JPEG')
        photos = [SimpleUploadedFile(f'{index}.jpg', content.getvalue(), content_type='image/jpeg') for index in range(2)]
        video = SimpleUploadedFile('result.webm', b'\x1a\x45\xdf\xa3' + b'0' * 32, content_type='video/webm')
        sent = self.client.post(f'/masters/api/requests/{self.request_item.id}/complete/', {
            'photos': photos, 'videos': [video], 'comment': 'Проверено давление',
        })
        self.assertEqual(sent.status_code, 200)
        self.request_item.refresh_from_db()
        self.assertEqual(self.request_item.completion_media.count(), 2)
        self.assertEqual(self.request_item.completion_comment, 'Проверено давление')
        self._approve()
        self.assertEqual(self.request_item.approved_total, 2300)
        self.assertEqual(self.request_item.approved_payout, 920)
        self.work.price = 5000
        self.work.save()
        earnings = self.client.get('/masters/api/earnings/').json()
        self.assertEqual(earnings['all_time']['earned'], 920)
        self.assertEqual(earnings['all_time']['count'], 1)
        self.assertEqual(earnings['recent'][0]['total'], 2300)

    def test_payment_cash_handover_and_qr_withdrawal_monday_only(self):
        self.client.force_login(self.master)
        url = f'/masters/api/requests/{self.request_item.id}/payment/'
        self.assertEqual(self.client.post(url, json.dumps({'method': 'cash'}), content_type='application/json').status_code, 404)
        self.request_item.assigned_to = self.master
        self.request_item.completion_status = ServiceRequest.CompletionStatus.PENDING
        self.request_item.save(update_fields=['assigned_to', 'completion_status'])
        self.assertEqual(self.client.post(f'/masters/api/requests/{self.request_item.pk}/payment/confirm/').status_code, 409)
        self.assertEqual(self.client.get(f'/masters/api/requests/{self.request_item.pk}/payment/qr/').status_code, 404)
        moderator = self._approve()
        self.assertEqual(self.client.post(url, json.dumps({'method': 'bank'}), content_type='application/json').status_code, 400)
        self.assertEqual(self.client.post(url, json.dumps({'method': 'cash'}), content_type='application/json').status_code, 200)
        self.assertEqual(self.client.post(url, json.dumps({'method': 'qr'}), content_type='application/json').status_code, 409)
        confirm_url = f'/masters/api/requests/{self.request_item.pk}/payment/confirm/'
        self.assertEqual(self.client.post(f'/masters/api/requests/{self.request_item.pk}/cash-report/').status_code, 409)
        self.assertEqual(self.client.get('/masters/api/earnings/').json()['cash_due'], 0)
        self.assertEqual(self.client.post(confirm_url).status_code, 200)
        self.assertEqual(self.client.post(confirm_url).status_code, 409)
        data = self.client.get('/masters/api/earnings/').json()
        self.assertEqual(data['cash_due'], 1380)
        self.assertEqual(data['available'], 0)
        self.assertEqual(self.client.post(f'/masters/api/requests/{self.request_item.pk}/cash-report/').status_code, 200)
        self.client.force_login(moderator)
        self.client.post('/admin/core/servicerequest/', {
            'action': 'confirm_cash', '_selected_action': [self.request_item.pk], 'index': '0',
        })
        self.client.force_login(self.master)
        self.assertEqual(self.client.get('/masters/api/earnings/').json()['cash_due'], 0)

        second = ServiceRequest.objects.create(phone='+79000000001', assigned_to=self.master, completion_status='pending')
        second.works.add(self.work)
        self.request_item = second
        self._approve()
        qr_url = f'/masters/api/requests/{second.pk}/payment/'
        self.assertEqual(self.client.post(qr_url, json.dumps({'method': 'qr'}), content_type='application/json').status_code, 200)
        qr_image = self.client.get(f'/masters/api/requests/{second.pk}/payment/qr/')
        self.assertEqual(qr_image.status_code, 200)
        self.assertTrue(qr_image.content.startswith(b'\x89PNG'))
        other = get_user_model().objects.create_user(username='other-payment', password='pass', is_staff=True)
        other.groups.add(Group.objects.get_or_create(name='masters')[0])
        self.client.force_login(other)
        self.assertEqual(self.client.get(f'/masters/api/requests/{second.pk}/payment/qr/').status_code, 404)
        self.assertEqual(self.client.post(f'/masters/api/requests/{second.pk}/payment/confirm/').status_code, 404)
        self.client.force_login(self.master)
        self.assertEqual(self.client.get('/masters/api/earnings/').json()['available'], 0)
        self.assertEqual(self.client.post(f'/masters/api/requests/{second.pk}/payment/confirm/').status_code, 200)
        self.assertEqual(self.client.get('/masters/api/earnings/').json()['available'], 920)
        demo_token = signing.dumps({'id': second.pk, 'amount': 2300}, salt='demo-payment')
        self.assertContains(self.client.get(f'/masters/demo-payment/{demo_token}/'), 'Деньги не списываются')
        with patch('core.views.timezone.localdate', return_value=date(2026, 10, 20)):
            self.assertEqual(self.client.post('/masters/api/withdrawals/').status_code, 403)
        with patch('core.views.timezone.localdate', return_value=date(2026, 10, 19)):
            self.assertEqual(self.client.post('/masters/api/withdrawals/').status_code, 200)
            self.assertEqual(self.client.post('/masters/api/withdrawals/').status_code, 409)
        self.assertEqual(WithdrawalRequest.objects.get(master=self.master).amount, 920)
        self.client.force_login(moderator)
        withdrawal = WithdrawalRequest.objects.get(master=self.master)
        self.client.post('/admin/core/withdrawalrequest/', {
            'action': 'approve_withdrawal', '_selected_action': [withdrawal.pk], 'index': '0',
        })
        withdrawal.refresh_from_db()
        self.assertEqual(withdrawal.status, WithdrawalRequest.Status.APPROVED)
        self.client.force_login(self.master)
        self.assertEqual(self.client.get('/masters/api/earnings/').json()['available'], 0)

    def test_rejected_withdrawal_releases_reserved_balance(self):
        self.request_item.assigned_to = self.master
        self.request_item.completion_status = ServiceRequest.CompletionStatus.PENDING
        self.request_item.save(update_fields=['assigned_to', 'completion_status'])
        moderator = self._approve()
        self.client.post(f'/masters/api/requests/{self.request_item.pk}/payment/', json.dumps({'method': 'qr'}), content_type='application/json')
        self.client.post(f'/masters/api/requests/{self.request_item.pk}/payment/confirm/')
        with patch('core.views.timezone.localdate', return_value=date(2026, 10, 19)):
            self.client.post('/masters/api/withdrawals/')
        self.client.force_login(moderator)
        withdrawal = WithdrawalRequest.objects.get(master=self.master)
        self.client.post('/admin/core/withdrawalrequest/', {
            'action': 'reject_withdrawal', '_selected_action': [withdrawal.pk], 'index': '0',
        })
        self.client.force_login(self.master)
        self.assertEqual(self.client.get('/masters/api/earnings/').json()['available'], 920)
