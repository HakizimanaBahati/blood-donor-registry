"""Generate a local HS256 test token for curl/API verification.

Usage (from repo root):
    .venv\\Scripts\\python.exe scripts\\make_test_token.py admin
    .venv\\Scripts\\python.exe scripts\\make_test_token.py hospital1

Only works when the backend is running in DEBUG mode with the clearly-marked
local development JWT secret. No real Supabase credentials are used.
"""
import os
import sys
import time
from pathlib import Path

import django
import jwt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.conf import settings  # noqa: E402

USERS = {
    "admin": "b0000000-0000-4000-8000-000000000001",
    "hospital1": "b0000000-0000-4000-8000-000000000002",
    "hospital2": "b0000000-0000-4000-8000-000000000003",
}

if __name__ == "__main__":
    role = sys.argv[1] if len(sys.argv) > 1 else "hospital1"
    if role not in USERS:
        raise SystemExit(f"Choose one of: {', '.join(USERS)}")
    if not settings.DEBUG:
        raise SystemExit("Refusing to mint a token when DEBUG is false")
    now = int(time.time())
    claims = {
        "sub": USERS[role],
        "aud": settings.SUPABASE_JWT_AUDIENCE,
        "iat": now - 10,
        "exp": now + 3600,
        "role": "authenticated",
    }
    if settings.SUPABASE_JWT_ISSUER:
        claims["iss"] = settings.SUPABASE_JWT_ISSUER
    print(jwt.encode(claims, settings.SUPABASE_JWT_SECRET, algorithm="HS256"))
