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

execute_from_command_line(
    ["manage.py", "runserver", "127.0.0.1:8000", "--noreload"]
)
