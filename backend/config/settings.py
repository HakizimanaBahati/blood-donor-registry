"""Settings for the Blood Donor Registry REST API.

All secrets come from environment variables (loaded from backend/.env in development).
There are no production credentials or keys in this repository.
"""
import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


DEBUG = env_bool("DJANGO_DEBUG", False)

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is false")
    SECRET_KEY = "local-development-only-secret-not-for-production"

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",")
    if host.strip()
]

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL and DEBUG:
    DATABASE_URL = os.getenv("TEST_DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL must be set when DJANGO_DEBUG is false; "
        "TEST_DATABASE_URL is only allowed in local development"
    )

DATABASES = {"default": dj_database_url.parse(DATABASE_URL, conn_max_age=0)}
DATABASES["default"].setdefault("OPTIONS", {})

# ── Applications ──────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "rest_framework",
    "corsheaders",
    "common",
    "authentication",
    "hospitals",
    "donors",
    "requests_app",
    "analytics",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "authentication.middleware.SupabaseClaimsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    }
]

# ── REST framework ────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "authentication.authentication.SupabaseJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "authentication.permissions.IsAuthenticatedUser",
    ],
    "DEFAULT_PAGINATION_CLASS": "common.pagination.StandardPagination",
    "PAGE_SIZE": 10,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "EXCEPTION_HANDLER": "common.errors.api_exception_handler",
    "UNAUTHENTICATED_USER": None,
}

# ── CORS: only the configured frontend origin(s) ──────────────────────────────
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]
CORS_ALLOW_CREDENTIALS = False

# ── CSRF / HTTPS hardening ────────────────────────────────────────────────────
# Trusted origins are supplied explicitly by the deployment environment when
# Django CSRF protection is needed. They are deliberately not derived from CORS,
# and no Render/Vercel domains are hardcoded here.
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

# HTTPS is terminated at Render initially. Do not redirect at the Django layer
# and do not trust X-Forwarded-Proto until Render's proxy behaviour is verified.
SECURE_SSL_REDIRECT = False
# SECURE_PROXY_SSL_HEADER is intentionally left unset.

# HSTS rolls out in later stages; includeSubDomains and preload require separate
# review because they affect every subdomain and can be difficult to reverse.
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# ── Supabase Auth / JWT verification ──────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "").strip()
SUPABASE_JWKS_URL = os.getenv("SUPABASE_JWKS_URL", "").strip()
SUPABASE_JWT_ISSUER = os.getenv("SUPABASE_JWT_ISSUER", "").strip()
SUPABASE_JWT_AUDIENCE = os.getenv("SUPABASE_JWT_AUDIENCE", "authenticated").strip()

if SUPABASE_URL:
    SUPABASE_JWKS_URL = SUPABASE_JWKS_URL or f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
    SUPABASE_JWT_ISSUER = SUPABASE_JWT_ISSUER or f"{SUPABASE_URL}/auth/v1"

# Only a clearly-marked development fallback; production requires explicit config.
if DEBUG and not SUPABASE_JWT_SECRET and not SUPABASE_JWKS_URL:
    SUPABASE_JWT_SECRET = "local-dev-only-jwt-secret-with-at-least-32-bytes"

JWT_ALGORITHMS = ("HS256", "RS256", "ES256")

# ── Misc ──────────────────────────────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"

TEST_RUNNER = "config.test_runner.DomainSchemaTestRunner"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        # Per-request auth diagnostics are useful locally but too noisy in production.
        "authentication": {
            "handlers": ["console"],
            "level": "INFO" if DEBUG else "WARNING",
            "propagate": False,
        },
    },
}
