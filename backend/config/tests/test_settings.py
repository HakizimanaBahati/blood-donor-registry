"""Isolated tests for settings safety and production hardening.

The settings module is executed in a fresh namespace with a controlled
environment; no real environment values are read, logged, or asserted, and no
database connection is made.
"""
import os
import runpy
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from django.http.request import validate_host
from django.test import RequestFactory, SimpleTestCase
from django.urls import resolve

from config.health import HealthView

SETTINGS_FILE = Path(__file__).resolve().parents[1] / "settings.py"

# Deliberately fake, non-secret values used only to identify which variable won.
PRIMARY_URL = "postgresql://primary_user@primary.example.invalid:5432/primary_db"
TEST_URL = "postgresql://test_user@test.example.invalid:5432/test_db"
DUMMY_SECRET = "settings-fallback-test-placeholder"

# Reserved example domains used only as configuration fixtures; these are not
# Render, Vercel, or project deployment domains.
CORS_ORIGIN = "https://frontend-cors.example.test"
TRUSTED_ORIGIN_ONE = "https://frontend-one.example.test"
TRUSTED_ORIGIN_TWO = "https://frontend-two.example.test"
EXPLICIT_HOST = "api.example.test"
SECOND_HOST = "www.example.test"

_ENV_KEYS = (
    "DATABASE_URL",
    "TEST_DATABASE_URL",
    "DJANGO_DEBUG",
    "DJANGO_SECRET_KEY",
    "DJANGO_ALLOWED_HOSTS",
    "CORS_ALLOWED_ORIGINS",
    "CSRF_TRUSTED_ORIGINS",
)


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


def _production_settings(**overrides):
    """Load settings with the minimum values required for production mode."""
    values = {
        "DATABASE_URL": PRIMARY_URL,
        "TEST_DATABASE_URL": TEST_URL,
        "DJANGO_DEBUG": "false",
        "DJANGO_SECRET_KEY": DUMMY_SECRET,
    }
    values.update(overrides)
    return _load_settings(**values)


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


class SecuritySettingsTests(SimpleTestCase):
    def test_security_middleware_immediately_follows_cors(self):
        loaded = _production_settings()
        middleware = loaded["MIDDLEWARE"]

        self.assertEqual(middleware[0], "corsheaders.middleware.CorsMiddleware")
        self.assertEqual(middleware[1], "django.middleware.security.SecurityMiddleware")
        self.assertIn("django.middleware.common.CommonMiddleware", middleware)
        self.assertIn("authentication.middleware.SupabaseClaimsMiddleware", middleware)
        self.assertLess(
            middleware.index("django.middleware.security.SecurityMiddleware"),
            middleware.index("authentication.middleware.SupabaseClaimsMiddleware"),
        )

    def test_production_enables_secure_cookies_without_ssl_redirect_or_proxy_header(self):
        loaded = _production_settings()

        self.assertTrue(loaded["SESSION_COOKIE_SECURE"])
        self.assertTrue(loaded["CSRF_COOKIE_SECURE"])
        self.assertFalse(loaded["SECURE_SSL_REDIRECT"])
        self.assertNotIn("SECURE_PROXY_SSL_HEADER", loaded)

    def test_local_debug_preserves_development_defaults(self):
        loaded = _load_settings(
            TEST_DATABASE_URL=TEST_URL,
            DJANGO_DEBUG="true",
            DJANGO_SECRET_KEY=DUMMY_SECRET,
        )

        self.assertFalse(loaded["SESSION_COOKIE_SECURE"])
        self.assertFalse(loaded["CSRF_COOKIE_SECURE"])
        self.assertFalse(loaded["SECURE_SSL_REDIRECT"])
        self.assertEqual(loaded["SECURE_HSTS_SECONDS"], 0)
        self.assertEqual(loaded["ALLOWED_HOSTS"], ["localhost", "127.0.0.1", "testserver"])
        self.assertEqual(loaded["CORS_ALLOWED_ORIGINS"], ["http://localhost:3000"])
        self.assertEqual(loaded["CSRF_TRUSTED_ORIGINS"], [])

    def test_cors_credentials_remain_disabled(self):
        loaded = _production_settings(CORS_ALLOWED_ORIGINS=CORS_ORIGIN)

        self.assertFalse(loaded["CORS_ALLOW_CREDENTIALS"])
        self.assertEqual(loaded["CORS_ALLOWED_ORIGINS"], [CORS_ORIGIN])
        self.assertNotIn("*", loaded["CORS_ALLOWED_ORIGINS"])

    def test_csrf_trusted_origins_come_only_from_explicit_environment(self):
        loaded = _production_settings(
            CORS_ALLOWED_ORIGINS=CORS_ORIGIN,
            CSRF_TRUSTED_ORIGINS=f" {TRUSTED_ORIGIN_ONE} , {TRUSTED_ORIGIN_TWO} ",
        )

        self.assertEqual(
            loaded["CSRF_TRUSTED_ORIGINS"],
            [TRUSTED_ORIGIN_ONE, TRUSTED_ORIGIN_TWO],
        )
        self.assertNotIn(CORS_ORIGIN, loaded["CSRF_TRUSTED_ORIGINS"])

    def test_csrf_trusted_origins_empty_when_not_supplied(self):
        loaded = _production_settings(CORS_ALLOWED_ORIGINS=CORS_ORIGIN)

        self.assertEqual(loaded["CSRF_TRUSTED_ORIGINS"], [])

    def test_hsts_is_initially_disabled(self):
        loaded = _production_settings()

        self.assertEqual(loaded["SECURE_HSTS_SECONDS"], 0)
        self.assertFalse(loaded["SECURE_HSTS_INCLUDE_SUBDOMAINS"])
        self.assertFalse(loaded["SECURE_HSTS_PRELOAD"])

    def test_security_header_defaults_are_explicit(self):
        loaded = _production_settings()

        self.assertTrue(loaded["SECURE_CONTENT_TYPE_NOSNIFF"])
        self.assertEqual(loaded["SECURE_REFERRER_POLICY"], "same-origin")
        self.assertEqual(loaded["SECURE_CROSS_ORIGIN_OPENER_POLICY"], "same-origin")
        self.assertEqual(loaded["X_FRAME_OPTIONS"], "DENY")

    def test_explicit_allowed_hosts_are_parsed_without_wildcard(self):
        loaded = _production_settings(
            DJANGO_ALLOWED_HOSTS=f" {EXPLICIT_HOST} , {SECOND_HOST} "
        )
        hosts = loaded["ALLOWED_HOSTS"]

        self.assertEqual(hosts, [EXPLICIT_HOST, SECOND_HOST])
        self.assertTrue(validate_host(EXPLICIT_HOST, hosts))
        self.assertFalse(validate_host("unknown.example.invalid", hosts))
        self.assertNotIn("*", hosts)

    def test_supabase_auth_configuration_is_unchanged(self):
        loaded = _production_settings()
        rest_framework = loaded["REST_FRAMEWORK"]

        self.assertEqual(
            rest_framework["DEFAULT_AUTHENTICATION_CLASSES"],
            ["authentication.authentication.SupabaseJWTAuthentication"],
        )
        self.assertEqual(
            rest_framework["DEFAULT_PERMISSION_CLASSES"],
            ["authentication.permissions.IsAuthenticatedUser"],
        )
        self.assertIsNone(rest_framework["UNAUTHENTICATED_USER"])
        self.assertEqual(loaded["JWT_ALGORITHMS"], ("HS256", "RS256", "ES256"))


class HealthEndpointTests(SimpleTestCase):
    def test_health_view_is_unauthenticated(self):
        self.assertEqual(HealthView.authentication_classes, [])
        self.assertEqual(HealthView.permission_classes, [])

    def test_health_view_returns_ok_without_database_access(self):
        request = RequestFactory().get("/health")
        response = HealthView.as_view()(request)
        response.render()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"status": "ok"})

    def test_health_route_resolves_to_health_view(self):
        match = resolve("/health")

        self.assertEqual(match.func.view_class, HealthView)
