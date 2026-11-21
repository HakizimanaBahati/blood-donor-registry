"""Shared helpers for automated tests. All tokens are generated locally with the
clearly-marked development secret; no real Supabase credentials are used.
"""
import json
import time
from uuid import UUID, uuid4

import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from django.conf import settings
from django.utils import timezone

ADMIN_ID = UUID("b0000000-0000-4000-8000-000000000001")
HOSPITAL_ONE_ID = UUID("b0000000-0000-4000-8000-000000000002")
HOSPITAL_TWO_ID = UUID("b0000000-0000-4000-8000-000000000003")
HOSPITAL_ONE = UUID("11111111-1111-4111-8111-111111111111")
HOSPITAL_TWO = UUID("22222222-2222-4222-8222-222222222222")
BREAK_IT_DONOR_ID = UUID("a0000006-0000-4000-8000-000000000006")
ELIGIBLE_DONOR_ID = UUID("a0000007-0000-4000-8000-000000000007")


def make_token(
    user_id: UUID | str = HOSPITAL_ONE_ID,
    *,
    secret: str | None = None,
    audience: str | None = None,
    issuer: str | None = None,
    expires_in: int = 3600,
    algorithm: str = "HS256",
    headers: dict | None = None,
    **extra_claims,
) -> str:
    now = int(time.time())
    claims = {
        "sub": str(user_id),
        "aud": audience if audience is not None else settings.SUPABASE_JWT_AUDIENCE,
        "iat": now - 10,
        "exp": now + expires_in,
        "role": "authenticated",
        "email": "test@example.invalid",
    }
    expected_issuer = issuer if issuer is not None else settings.SUPABASE_JWT_ISSUER
    if expected_issuer:
        claims["iss"] = expected_issuer
    claims.update(extra_claims)
    return jwt.encode(
        claims,
        secret if secret is not None else settings.SUPABASE_JWT_SECRET,
        algorithm=algorithm,
        headers=headers or {},
    )


def auth_headers(user_id: UUID | str = HOSPITAL_ONE_ID, **kwargs) -> dict:
    return {"HTTP_AUTHORIZATION": f"Bearer {make_token(user_id, **kwargs)}"}


ES256_TEST_KID = "test-es256-kid"


def generate_es256_keypair():
    private_key = ec.generate_private_key(ec.SECP256R1())
    return private_key, private_key.public_key()


def make_es256_token(
    user_id: UUID | str = HOSPITAL_ONE_ID,
    *,
    private_key,
    kid: str = ES256_TEST_KID,
    audience: str | None = None,
    issuer: str | None = None,
    expires_in: int = 3600,
    algorithm: str = "ES256",
    headers: dict | None = None,
    include_kid: bool = True,
    **extra_claims,
) -> str:
    now = int(time.time())
    claims = {
        "sub": str(user_id),
        "aud": audience if audience is not None else settings.SUPABASE_JWT_AUDIENCE,
        "iat": now - 10,
        "exp": now + expires_in,
        "role": "authenticated",
        "email": "test@example.invalid",
    }
    expected_issuer = issuer if issuer is not None else settings.SUPABASE_JWT_ISSUER
    if expected_issuer:
        claims["iss"] = expected_issuer
    claims.update(extra_claims)

    token_headers = {} if headers is None else dict(headers)
    if include_kid:
        token_headers.setdefault("kid", kid)
    return jwt.encode(claims, private_key, algorithm=algorithm, headers=token_headers)


def es256_auth_headers(user_id: UUID | str = HOSPITAL_ONE_ID, **kwargs) -> dict:
    return {"HTTP_AUTHORIZATION": f"Bearer {make_es256_token(user_id, **kwargs)}"}


class _MockSigningKey:
    def __init__(self, key):
        self.key = key


class MockJWKClient:
    def __init__(self, *, key=None, exc: Exception | None = None):
        self._key = key
        self._exc = exc
        self.calls = []

    def get_signing_key_from_jwt(self, token):
        self.calls.append(token)
        if self._exc is not None:
            raise self._exc
        return _MockSigningKey(self._key)


def unique_phone() -> str:
    return f"+1555{uuid4().int % 10_000_000_000:010d}"


def create_donor(**overrides):
    from donors.models import Donor

    now = timezone.now()
    payload = {
        "name": "[TEST] Helper Donor",
        "blood_type": "O+",
        "phone": unique_phone(),
        "last_donation": None,
        "created_at": now,
        "updated_at": now,
    }
    payload.update(overrides)
    return Donor.objects.create(**payload)


def create_request(**overrides):
    from requests_app.models import BloodRequest

    now = timezone.now()
    payload = {
        "hospital_id": HOSPITAL_ONE,
        "blood_type": "O+",
        "units": 2,
        "status": "pending",
        "created_at": now,
        "updated_at": now,
    }
    payload.update(overrides)
    return BloodRequest.objects.create(**payload)
