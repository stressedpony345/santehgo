import json
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image

from .models import Category, ServiceRequest, SubCategory, Work


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
