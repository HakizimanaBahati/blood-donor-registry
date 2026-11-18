"""Test runner that builds the real Supabase schema in the Django test database.

Domain tables are unmanaged (the SQL migrations own them), so Django's migrate step
does not create them. After the test database is set up we apply the same SQL files
used for Supabase, plus the local-only auth emulation and seed data.
"""
from pathlib import Path

from django.db import connection
from django.test.runner import DiscoverRunner

REPO_ROOT = Path(__file__).resolve().parents[2]


class DomainSchemaTestRunner(DiscoverRunner):
    def setup_databases(self, **kwargs):
        databases = super().setup_databases(**kwargs)
        self._apply("supabase/local/0000_auth_emulation.sql")
        for migration in sorted((REPO_ROOT / "supabase" / "migrations").glob("*.sql")):
            self._apply(str(migration.relative_to(REPO_ROOT)).replace("\\", "/"))
        self._apply("supabase/seed.sql")
        self._apply("supabase/local/seed_auth_users.sql")
        return databases

    @staticmethod
    def _apply(relative_path: str) -> None:
        sql = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        with connection.cursor() as cursor:
            cursor.execute(sql)
