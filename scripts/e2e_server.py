"""Prepare an isolated database and run Django for Playwright."""

from __future__ import annotations

import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / ".tmp" / "e2e.sqlite3"

os.environ.update(
    {
        "DJANGO_SETTINGS_MODULE": "config.settings",
        "DJANGO_DEBUG": "true",
        "DJANGO_ALLOWED_HOSTS": "127.0.0.1,localhost",
        "DJANGO_DB_PATH": str(DATABASE_PATH),
        "DADATA_API_TOKEN": "",
        "LEGAL_OPERATOR_NAME": "Тестовый оператор САНТЕХГО",
        "LEGAL_CONTACT_EMAIL": "privacy@example.test",
        "PERSONAL_DATA_CONSENT_VERSION": "e2e-1",
        "PERSONAL_DATA_CONSENT_EFFECTIVE_DATE": "05.11.2026",
    }
)

sys.path.insert(0, str(PROJECT_ROOT))

import django  # noqa: E402
from django.core.management import call_command, execute_from_command_line  # noqa: E402


DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
if os.environ.get("E2E_REUSE_DB") != "1":
    DATABASE_PATH.unlink(missing_ok=True)

django.setup()
call_command("migrate", interactive=False, verbosity=1)
call_command(
    "loaddata",
    str(PROJECT_ROOT / "tests" / "e2e" / "fixtures" / "catalog.json"),
    verbosity=1,
)

from django.contrib.auth import get_user_model  # noqa: E402
from django.contrib.auth.models import Group  # noqa: E402
from django.utils import timezone  # noqa: E402
from core.models import ServiceRequest  # noqa: E402

master_group, _ = Group.objects.get_or_create(name='masters')
master, _ = get_user_model().objects.get_or_create(
    username='e2e-master',
    defaults={'is_active': True, 'is_staff': True},
)
master.set_password('E2e-master-pass-2026')
master.is_active = True
master.is_staff = True
master.save()
master.groups.add(master_group)
if not ServiceRequest.objects.filter(phone='+79000000011').exists():
    ServiceRequest.objects.create(
        full_name='Клиент из общей очереди',
        phone='+79000000011',
        issue='Течёт смеситель на кухне',
        address='г. Челябинск, ул. Тестовая, 11',
        preferred_time='Сегодня после 18:00',
    )
if not ServiceRequest.objects.filter(phone='+79000000013').exists():
    ServiceRequest.objects.create(
        full_name='Второй клиент очереди',
        phone='+79000000013',
        issue='Установить стиральную машину',
        address='г. Челябинск, ул. Тестовая, 13',
        preferred_time='В выходные',
    )
if not ServiceRequest.objects.filter(phone='+79000000012').exists():
    ServiceRequest.objects.create(
        full_name='Клиент в работе',
        phone='+79000000012',
        issue='Заменить сифон',
        address='г. Челябинск, ул. Тестовая, 12',
        preferred_time='Завтра утром',
        assigned_to=master,
        assigned_at=timezone.now(),
        work_started_at=timezone.now(),
    )

execute_from_command_line(
    ["manage.py", "runserver", "127.0.0.1:8000", "--noreload"]
)
