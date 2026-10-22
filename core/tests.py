import json
from io import BytesIO
from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from PIL import Image

from .models import Category, ServiceRequest, SubCategory, WithdrawalRequest, Work


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

    def test_request_accepts_multiple_services(self):
        response = self.client.post(
            '/api/requests/',
            data=json.dumps({
                'full_name': 'Тестовый клиент',
                'phone': '+7 999 123-45-67',
                'subcategory_ids': [self.first.id, self.second.id],
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['success_url'], '/request-success/')
        request = ServiceRequest.objects.get()
        self.assertEqual(request.subcategories.count(), 2)

    def test_request_accepts_works_from_different_services(self):
        response = self.client.post(
            '/api/requests/',
            data=json.dumps({
                'full_name': 'Тестовый клиент',
                'phone': '+7 999 123-45-67',
                'work_ids': [self.first_work.id, self.second_work.id],
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        request = ServiceRequest.objects.get()
        self.assertEqual(request.works.count(), 2)
        self.assertEqual(request.subcategories.count(), 2)

    def test_request_success_page(self):
        response = self.client.get('/request-success/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Заявка принята')
        self.assertContains(response, 'Вернуться на главную')


class MasterAppTests(TestCase):
    def setUp(self):
        self.master = get_user_model().objects.create_user(
            username='master-test',
            password='Strong-test-pass-2026',
            is_staff=True,
        )
        category = Category.objects.create(name='Сантехника', slug='master-test')
        service = SubCategory.objects.create(category=category, name='Ремонт', approximate_price=1500)
        self.work = Work.objects.create(service=service, name='Замена крана', price=2300)
        self.request_item = ServiceRequest.objects.create(phone='+79000000000', issue='Течёт кран')
        self.request_item.subcategories.add(service)
        self.request_item.works.add(self.work)

    def test_master_pages_require_login(self):
        response = self.client.get('/masters/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/masters/login/', response.url)

    def test_master_can_claim_request(self):
        self.client.force_login(self.master)
        queue = self.client.get('/masters/api/requests/').json()
        self.assertEqual(queue['available'][0]['price'], 2300)

        response = self.client.post(f'/masters/api/requests/{self.request_item.id}/claim/')
        self.assertEqual(response.status_code, 200)
        self.request_item.refresh_from_db()
        self.assertEqual(self.request_item.assigned_to, self.master)

    def test_manifest_is_available(self):
        response = self.client.get('/masters/manifest.webmanifest')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['start_url'], '/masters/')

    def test_master_adds_catalog_and_custom_work_to_claimed_request(self):
        self.client.force_login(self.master)
        self.client.post(f'/masters/api/requests/{self.request_item.id}/claim/')
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
        for invalid in ({'name': '', 'price': 500}, {'name': 'Тест', 'price': -1}, {'work_id': 999999}):
            self.assertEqual(self.client.post(url, json.dumps(invalid), content_type='application/json').status_code, 400)
        other = get_user_model().objects.create_user(username='other-master', password='pass', is_staff=True)
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
        ServiceRequest.objects.create(phone='+79000000002')
        ServiceRequest.objects.create(phone='+79000000003', completion_status=ServiceRequest.CompletionStatus.APPROVED, is_processed=True)
        ServiceRequest.objects.create(phone='+79000000004', completion_status=ServiceRequest.CompletionStatus.PENDING, assigned_to=self.master)
        self.client.force_login(moderator)
        listing = self.client.get('/admin/core/servicerequest/')
        self.assertEqual(listing.status_code, 200)
        detail = self.client.get(f'/admin/core/servicerequest/{self.request_item.pk}/change/')
        self.assertEqual(detail.status_code, 200)
        call_command('check_master_admin')

    def test_completion_media_approval_and_frozen_40_percent(self):
        self.client.force_login(self.master)
        self.client.post(f'/masters/api/requests/{self.request_item.id}/claim/')
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
        moderator = self._approve()
        self.assertEqual(self.client.post(url, json.dumps({'method': 'bank'}), content_type='application/json').status_code, 400)
        self.assertEqual(self.client.post(url, json.dumps({'method': 'cash'}), content_type='application/json').status_code, 200)
        self.assertEqual(self.client.post(url, json.dumps({'method': 'qr'}), content_type='application/json').status_code, 409)
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
        self.assertEqual(self.client.get('/masters/api/earnings/').json()['available'], 920)
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
        with patch('core.views.timezone.localdate', return_value=date(2026, 10, 19)):
            self.client.post('/masters/api/withdrawals/')
        self.client.force_login(moderator)
        withdrawal = WithdrawalRequest.objects.get(master=self.master)
        self.client.post('/admin/core/withdrawalrequest/', {
            'action': 'reject_withdrawal', '_selected_action': [withdrawal.pk], 'index': '0',
        })
        self.client.force_login(self.master)
        self.assertEqual(self.client.get('/masters/api/earnings/').json()['available'], 920)
