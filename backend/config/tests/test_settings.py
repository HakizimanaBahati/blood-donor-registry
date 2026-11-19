"""Isolated tests for DATABASE_URL / TEST_DATABASE_URL fallback behaviour.

The settings module is executed in a fresh namespace with a controlled
environment; no real environment values are read, logged, or asserted, and no
database connection is made.
"""
import os
import runpy
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

SETTINGS_FILE = Path(__file__).resolve().parents[1] / "settings.py"

# Deliberately fake, non-secret values used only to identify which variable won.
PRIMARY_URL = "postgresql://primary_user@primary.example.invalid:5432/primary_db"
TEST_URL = "postgresql://test_user@test.example.invalid:5432/test_db"
DUMMY_SECRET = "settings-fallback-test-placeholder"

_ENV_KEYS = ("DATABASE_URL", "TEST_DATABASE_URL", "DJANGO_DEBUG", "DJANGO_SECRET_KEY")


@contextmanager
def _controlled_env(**values):
    """Temporarily replace only the variables these tests care about."""
    saved = {key: os.environ.get(key) for key in _ENV_KEYS}
    try:
        for key in _ENV_KEYS:
            os.environ.pop(key, None)
        os.environ.update(values)
        yield
    finally:
        for key in _ENV_KEYS:
            os.environ.pop(key, None)
        for key, value in saved.items():
            if value is not None:
                os.environ[key] = value


def _load_settings(**values):
    """Execute settings.py with a controlled env and without loading .env."""
    with _controlled_env(**values), patch("dotenv.load_dotenv"):
        return runpy.run_path(str(SETTINGS_FILE))


class DatabaseUrlFallbackTests(SimpleTestCase):
    def test_debug_true_with_database_url_uses_database_url(self):
        loaded = _load_settings(
            DATABASE_URL=PRIMARY_URL,
            TEST_DATABASE_URL=TEST_URL,
            DJANGO_DEBUG="true",
            DJANGO_SECRET_KEY=DUMMY_SECRET,
        )
        self.assertEqual(loaded["DATABASE_URL"], PRIMARY_URL)

    def test_debug_true_without_database_url_uses_test_database_url(self):
        loaded = _load_settings(
            TEST_DATABASE_URL=TEST_URL,
            DJANGO_DEBUG="true",
            DJANGO_SECRET_KEY=DUMMY_SECRET,
        )
        self.assertEqual(loaded["DATABASE_URL"], TEST_URL)

    def test_debug_false_without_database_url_raises(self):
        with self.assertRaisesRegex(
            RuntimeError, "DATABASE_URL must be set when DJANGO_DEBUG is false"
        ):
            _load_settings(
                TEST_DATABASE_URL=TEST_URL,
                DJANGO_DEBUG="false",
                DJANGO_SECRET_KEY=DUMMY_SECRET,
            )

    def test_debug_false_with_database_url_uses_database_url(self):
        loaded = _load_settings(
            DATABASE_URL=PRIMARY_URL,
            TEST_DATABASE_URL=TEST_URL,
            DJANGO_DEBUG="false",
            DJANGO_SECRET_KEY=DUMMY_SECRET,
        )
        self.assertEqual(loaded["DATABASE_URL"], PRIMARY_URL)
