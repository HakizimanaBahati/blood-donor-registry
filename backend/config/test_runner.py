"""Test runner that builds the real Supabase schema in the Django test database.

Domain tables are unmanaged (the SQL migrations own them), so Django's migrate step
does not create them. After the test database is set up we apply the same SQL files
used for Supabase, plus the local-only auth emulation and seed data.

Django creates its temporary database with the *default* connection settings. Since
the application now points at the live Supabase pooler (whose role cannot create
databases), the runner first switches the connection to TEST_DATABASE_URL — the
isolated local cluster — so tests can never touch production data.
"""
import os
from pathlib import Path

import dj_database_url
from django.conf import settings
from django.db import connections
from django.test.runner import DiscoverRunner

REPO_ROOT = Path(__file__).resolve().parents[2]


class DomainSchemaTestRunner(DiscoverRunner):
    def setup_databases(self, **kwargs):
        self._use_local_test_database()
        databases = super().setup_databases(**kwargs)
        self._apply("supabase/local/0000_auth_emulation.sql")
        for migration in sorted((REPO_ROOT / "supabase" / "migrations").glob("*.sql")):
            self._apply(str(migration.relative_to(REPO_ROOT)).replace("\\", "/"))
        self._apply("supabase/seed.sql")
        self._apply("supabase/local/seed_auth_users.sql")
        return databases

    @staticmethod
    def _use_local_test_database() -> None:
        test_url = os.getenv("TEST_DATABASE_URL", "").strip()
        if not test_url:
            return
        test_config = dj_database_url.parse(test_url, conn_max_age=0)
        test_config.setdefault("OPTIONS", {})
        settings.DATABASES["default"].update(test_config)
        connection = connections["default"]
        connection.close()
        connection.settings_dict.update(test_config)

    @staticmethod
    def _apply(relative_path: str) -> None:
        sql = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        with connections["default"].cursor() as cursor:
            cursor.execute(sql)
