"""Supabase access-token verification.

Supports the legacy HS256 shared secret and modern asymmetric keys (RS256/ES256)
distributed through the Supabase JWKS endpoint. Signature, algorithm, issuer,
audience, expiry and required claims are always verified.
"""
import logging
import re
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


_SANITIZED_MESSAGE_LIMIT = 200
_REDACTED = "[REDACTED]"

# Exceptions occasionally echo token material. Strip it before it reaches any log sink.
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[^\s,;]+")
_JWT_RE = re.compile(r"[A-Za-z0-9_-]{2,}\.[A-Za-z0-9_-]{2,}\.[A-Za-z0-9_-]{2,}")
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b([a-z0-9_]*(?:secret|token|password|passwd|pwd|api[_-]?key|apikey|credential|private[_-]?key|database_url|authorization|auth|jwt|claims|sub|aud|iss|exp|iat|email|role|app_metadata|user_metadata|kid|alg|typ)[a-z0-9_]*)\b[\"']?\s*[:=]\s*(\"[^\"]*\"|'[^']*'|[^\s,;}]+)"
)
_SECRET_PREFIX_RE = re.compile(r"(?i)\b(?:sk|rk)_[A-Za-z0-9_-]{8,}\b|\bsb_secret_[A-Za-z0-9_-]{8,}\b")
_UUID_RE = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_OPAQUE_TOKEN_RE = re.compile(
    r"\b(?=[A-Za-z0-9_-]{16,}\b)(?=[A-Za-z0-9_-]*[A-Za-z])(?=[A-Za-z0-9_-]*[0-9_-])[A-Za-z0-9_-]+\b"
)
_KNOWN_SECRET_SETTINGS = (
    "SUPABASE_JWT_SECRET",
    "DJANGO_SECRET_KEY",
    "DATABASE_URL",
    "TEST_DATABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SERVICE_ROLE_KEY",
)


def _sanitize_log_field(value: object, *, limit: int = 80) -> str:
    """Keep attacker-controlled diagnostic fields on one short log line."""
    text = "" if value is None else str(value)
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        text = text[: limit - 3] + "..."
    return text or "<empty>"


def _sanitize_exception_message(exc: Exception) -> str:
    """Return a short, non-sensitive summary of an exception for diagnostics."""
    message = str(exc)
    if not message:
        return "<empty>"

    # Keep each log record on one line and avoid log-injection via control characters.
    message = re.sub(r"[\x00-\x1f\x7f]+", " ", message)
    message = re.sub(r"\s+", " ", message).strip()

    # An exception may embed a configured secret verbatim; never echo those values.
    for setting_name in _KNOWN_SECRET_SETTINGS:
        value = getattr(settings, setting_name, "")
        if isinstance(value, str) and len(value) >= 4:
            message = message.replace(value, _REDACTED)

    message = _BEARER_RE.sub(_REDACTED, message)
    message = _JWT_RE.sub(_REDACTED, message)
    message = _SECRET_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}={_REDACTED}", message)
    message = _SECRET_PREFIX_RE.sub(_REDACTED, message)
    message = _UUID_RE.sub(_REDACTED, message)
    message = _EMAIL_RE.sub(_REDACTED, message)
    message = _OPAQUE_TOKEN_RE.sub(_REDACTED, message)
    message = re.sub(r"\s+", " ", message).strip()

    if len(message) > _SANITIZED_MESSAGE_LIMIT:
        message = message[: _SANITIZED_MESSAGE_LIMIT - 3] + "..."
    return message or "<empty>"


def _log_verification_failure(*, category: str, algorithm: str | None, kid_present: bool | None, exc: Exception) -> None:
    jwks_host = _sanitize_log_field(_jwks_host())
    error_class = _sanitize_log_field(type(exc).__name__)
    error_message = _sanitize_exception_message(exc)
    safe_category = _sanitize_log_field(category)
    safe_algorithm = _sanitize_log_field(algorithm)
    logger.warning(
        "Supabase JWT verification failed category=%s algorithm=%s kid_present=%s jwt_error_class=%s jwt_jwks_host=%s jwt_error_message=%s",
        safe_category,
        safe_algorithm,
        kid_present,
        error_class,
        jwks_host,
        error_message,
        extra={
            "jwt_failure_category": safe_category,
            "jwt_algorithm": safe_algorithm,
            "jwt_kid_present": kid_present,
            "jwt_jwks_host": jwks_host,
            "jwt_error_class": error_class,
            "jwt_error_message": error_message,
        },
    )


_jwk_client_instance: PyJWKClient | None = None
_jwk_client_url: str | None = None


def _jwk_client() -> PyJWKClient:
    global _jwk_client_instance, _jwk_client_url
    url = settings.SUPABASE_JWKS_URL
    if not url:
        raise SupabaseTokenError("Asymmetric token verification is not configured")
    if _jwk_client_instance is None or _jwk_client_url != url:
        _jwk_client_instance = PyJWKClient(url, cache_keys=True, lifespan=3600)
        _jwk_client_url = url
    return _jwk_client_instance


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
    except TypeError as exc:  # Unexpected argument/type errors are not JWKS retrieval failures
        raise _fail(
            "Access token verification is temporarily unavailable",
            category="unexpected_type_error",
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
