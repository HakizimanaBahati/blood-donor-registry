"""Propagate the verified Supabase identity into the database session.

Supabase RLS helpers read request.jwt.claim.sub. Setting it transaction-locally means
RLS policies can be applied to Django queries as well whenever the configured database
role is subject to RLS (a restricted backend role is recommended in production).
"""
import logging
import uuid

from django.db import connection, transaction

from authentication.jwt import SupabaseTokenError, verify_access_token

logger = logging.getLogger(__name__)


class SupabaseClaimsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.auth_debug_request_id = uuid.uuid4().hex[:12]
        verified = None
        header = request.META.get("HTTP_AUTHORIZATION", "")
        header_present = bool(header)
        scheme = header.split(None, 1)[0] if header else ""
        logger.info(
            "Auth.middleware invoked",
            extra={
                "auth_path": request.path,
                "auth_method": request.method,
                "auth_request_id": request.auth_debug_request_id,
                "auth_header_present": header_present,
                "auth_scheme": scheme,
                "auth_logger_name": logger.name,
                "auth_logger_effective_level": logging.getLevelName(logger.getEffectiveLevel()),
            },
        )
        if header.lower().startswith("bearer "):
            token = header.split(None, 1)[1].strip()
            try:
                verified = verify_access_token(token)
            except SupabaseTokenError as exc:
                verified = None  # DRF will produce the correct 401 response later
                request.supabase_auth_error = exc
            else:
                request.verified_token = verified
                request.supabase_auth_error = None

        with transaction.atomic():
            if verified:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('request.jwt.claim.sub', %s, true)",
                        [verified.subject],
                    )
                    cursor.execute(
                        "SELECT set_config('request.jwt.claim.role', %s, true)",
                        ["authenticated"],
                    )
                    cursor.execute("SET LOCAL ROLE authenticated")
            try:
                response = self.get_response(request)
            except Exception:
                transaction.set_rollback(True)
                raise
            status_code = getattr(response, "status_code", None)
            if isinstance(status_code, int) and status_code >= 500:
                transaction.set_rollback(True)
            return response
