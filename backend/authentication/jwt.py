"""Supabase access-token verification.

Supports the legacy HS256 shared secret and modern asymmetric keys (RS256/ES256)
distributed through the Supabase JWKS endpoint. Signature, algorithm, issuer,
audience, expiry and required claims are always verified.
"""
import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

import jwt
from django.conf import settings
from jwt import PyJWKClient

logger = logging.getLogger(__name__)


class SupabaseTokenError(Exception):
    """Raised when a token cannot be trusted. Messages are safe for API responses."""


@dataclass(frozen=True)
class VerifiedToken:
    subject: str
    claims: dict[str, Any]


def _jwks_host() -> str | None:
    url = getattr(settings, "SUPABASE_JWKS_URL", "")
    if not url:
        return None
    hostname = urlparse(url).hostname
    return hostname or None


def _log_verification_failure(*, category: str, algorithm: str | None, kid_present: bool | None, exc: Exception) -> None:
    logger.warning(
        "Supabase JWT verification failed",
        extra={
            "jwt_failure_category": category,
            "jwt_algorithm": algorithm,
            "jwt_kid_present": kid_present,
            "jwt_jwks_host": _jwks_host(),
            "jwt_error_class": type(exc).__name__,
        },
    )


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


def _fail(
    message: str,
    *,
    category: str,
    algorithm: str | None,
    kid_present: bool | None,
    exc: Exception | None = None,
) -> "SupabaseTokenError":
    error = SupabaseTokenError(message)
    _log_verification_failure(
        category=category,
        algorithm=algorithm,
        kid_present=kid_present,
        exc=exc or error,
    )
    return error


def verify_access_token(token: str) -> VerifiedToken:
    algorithm: str | None = None
    kid_present: bool | None = None

    if not token or not isinstance(token, str):
        raise _fail(
            "Access token is missing",
            category="missing",
            algorithm=algorithm,
            kid_present=kid_present,
        )

    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise _fail(
            "Access token is malformed",
            category="malformed",
            algorithm=algorithm,
            kid_present=kid_present,
            exc=exc,
        ) from exc

    algorithm = header.get("alg")
    kid_present = "kid" in header

    if algorithm not in settings.JWT_ALGORITHMS:
        raise _fail(
            "Access token uses an unsupported signing algorithm",
            category="unsupported_algorithm",
            algorithm=algorithm,
            kid_present=kid_present,
        )
    if algorithm == "none":
        raise _fail(
            "Unsigned access tokens are not accepted",
            category="unsigned",
            algorithm=algorithm,
            kid_present=kid_present,
        )

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
                raise _fail(
                    "HS256 token verification is not configured",
                    category="misconfiguration",
                    algorithm=algorithm,
                    kid_present=kid_present,
                )
            claims = jwt.decode(token, settings.SUPABASE_JWT_SECRET, **decode_kwargs)
        else:
            signing_key = _jwk_client().get_signing_key_from_jwt(token).key
            claims = jwt.decode(token, signing_key, **decode_kwargs)
    except SupabaseTokenError:
        raise
    except jwt.ExpiredSignatureError as exc:
        raise _fail(
            "Access token has expired",
            category="expired",
            algorithm=algorithm,
            kid_present=kid_present,
            exc=exc,
        ) from exc
    except jwt.InvalidAudienceError as exc:
        raise _fail(
            "Access token has an invalid audience",
            category="audience",
            algorithm=algorithm,
            kid_present=kid_present,
            exc=exc,
        ) from exc
    except jwt.InvalidIssuerError as exc:
        raise _fail(
            "Access token has an invalid issuer",
            category="issuer",
            algorithm=algorithm,
            kid_present=kid_present,
            exc=exc,
        ) from exc
    except jwt.InvalidSignatureError as exc:
        raise _fail(
            "Access token signature is invalid",
            category="signature",
            algorithm=algorithm,
            kid_present=kid_present,
            exc=exc,
        ) from exc
    except jwt.PyJWTError as exc:
        raise _fail(
            "Access token verification failed",
            category="verification",
            algorithm=algorithm,
            kid_present=kid_present,
            exc=exc,
        ) from exc
    except Exception as exc:  # JWKS/network failures must not leak internal details
        raise _fail(
            "Access token verification is temporarily unavailable",
            category="jwks_retrieval",
            algorithm=algorithm,
            kid_present=kid_present,
            exc=exc,
        ) from exc

    subject = str(claims.get("sub", ""))
    try:
        UUID(subject)
    except (ValueError, AttributeError) as exc:
        raise _fail(
            "Access token has an invalid subject",
            category="subject",
            algorithm=algorithm,
            kid_present=kid_present,
            exc=exc,
        ) from exc

    return VerifiedToken(subject=subject, claims=claims)
