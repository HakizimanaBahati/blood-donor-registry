"""Supabase access-token verification.

Supports the legacy HS256 shared secret and modern asymmetric keys (RS256/ES256)
distributed through the Supabase JWKS endpoint. Signature, algorithm, issuer,
audience, expiry and required claims are always verified.
"""
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import jwt
from django.conf import settings
from jwt import PyJWKClient


class SupabaseTokenError(Exception):
    """Raised when a token cannot be trusted. Messages are safe for API responses."""


@dataclass(frozen=True)
class VerifiedToken:
    subject: str
    claims: dict[str, Any]


_jwk_client: PyJWKClient | None = None
_jwk_client_url: str | None = None


def _jwk_client() -> PyJWKClient:
    global _jwk_client, _jwk_client_url
    url = settings.SUPABASE_JWKS_URL
    if not url:
        raise SupabaseTokenError("Asymmetric token verification is not configured")
    if _jwk_client is None or _jwk_client_url != url:
        _jwk_client = PyJWKClient(url, cache_keys=True, lifespan=3600)
        _jwk_client_url = url
    return _jwk_client


def verify_access_token(token: str) -> VerifiedToken:
    if not token or not isinstance(token, str):
        raise SupabaseTokenError("Access token is missing")

    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise SupabaseTokenError("Access token is malformed") from exc

    algorithm = header.get("alg")
    if algorithm not in settings.JWT_ALGORITHMS:
        raise SupabaseTokenError("Access token uses an unsupported signing algorithm")
    if algorithm == "none":
        raise SupabaseTokenError("Unsigned access tokens are not accepted")

    options = {
        "require": ["exp", "sub", "iat"],
        "verify_signature": True,
        "verify_exp": True,
        "verify_aud": True,
        "verify_iss": True,
    }
    decode_kwargs: dict[str, Any] = {
        "algorithms": [algorithm],
        "audience": settings.SUPABASE_JWT_AUDIENCE,
        "options": options,
    }
    if settings.SUPABASE_JWT_ISSUER:
        decode_kwargs["issuer"] = settings.SUPABASE_JWT_ISSUER

    try:
        if algorithm == "HS256":
            if not settings.SUPABASE_JWT_SECRET:
                raise SupabaseTokenError("HS256 token verification is not configured")
            claims = jwt.decode(token, settings.SUPABASE_JWT_SECRET, **decode_kwargs)
        else:
            signing_key = _jwk_client().get_signing_key_from_jwt(token).key
            claims = jwt.decode(token, signing_key, **decode_kwargs)
    except jwt.ExpiredSignatureError as exc:
        raise SupabaseTokenError("Access token has expired") from exc
    except jwt.InvalidAudienceError as exc:
        raise SupabaseTokenError("Access token has an invalid audience") from exc
    except jwt.InvalidIssuerError as exc:
        raise SupabaseTokenError("Access token has an invalid issuer") from exc
    except jwt.InvalidSignatureError as exc:
        raise SupabaseTokenError("Access token signature is invalid") from exc
    except jwt.PyJWTError as exc:
        raise SupabaseTokenError("Access token verification failed") from exc
    except Exception as exc:  # JWKS/network failures must not leak internal details
        raise SupabaseTokenError("Access token verification is temporarily unavailable") from exc

    subject = str(claims.get("sub", ""))
    try:
        UUID(subject)
    except (ValueError, AttributeError) as exc:
        raise SupabaseTokenError("Access token has an invalid subject") from exc

    return VerifiedToken(subject=subject, claims=claims)
