import logging

from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied

from authentication.jwt import SupabaseTokenError, verify_access_token
from authentication.services import get_app_user

logger = logging.getLogger(__name__)


class SupabaseJWTAuthentication(BaseAuthentication):
    """Authenticate a Supabase-issued bearer token and resolve the local app role."""

    keyword = "Bearer"

    def authenticate(self, request):
        header = get_authorization_header(request)
        raw_header_present = bool(header)
        parts = header.split() if header else []
        scheme = parts[0].decode("ascii", "ignore") if parts else ""
        token_present = len(parts) == 2 and bool(parts[1])
        request_id = getattr(request, "auth_debug_request_id", None)

        logger.info(
            "Auth.authenticate invoked",
            extra={
                "auth_path": request.path,
                "auth_method": request.method,
                "auth_request_id": request_id,
                "auth_header_present": raw_header_present,
                "auth_scheme": scheme,
                "auth_token_present": token_present,
                "auth_logger_name": logger.name,
                "auth_logger_effective_level": logging.getLevelName(logger.getEffectiveLevel()),
            },
        )

        if not header:
            return None

        if len(parts) != 2 or scheme.lower() != self.keyword.lower():
            logger.warning(
                "Authentication failed: malformed Authorization header",
                extra={
                    "auth_path": request.path,
                    "auth_method": request.method,
                    "auth_request_id": request_id,
                    "auth_header_parts": len(parts),
                },
            )
            raise AuthenticationFailed("Authorization header must use the Bearer scheme.")

        try:
            token = parts[1].decode("ascii")
        except UnicodeDecodeError as exc:
            logger.warning(
                "Authentication failed: undecodable Authorization token",
                extra={"auth_path": request.path, "auth_method": request.method, "auth_request_id": request_id},
            )
            raise AuthenticationFailed("Authorization token contains invalid characters.") from exc

        # The middleware may already have verified this token for RLS claims.
        verified = getattr(request, "verified_token", None)
        auth_error = getattr(request, "supabase_auth_error", None)
        if verified is None and auth_error is not None:
            raise AuthenticationFailed(str(auth_error)) from auth_error
        if verified is None:
            try:
                verified = verify_access_token(token)
            except SupabaseTokenError as exc:
                raise AuthenticationFailed(str(exc)) from exc

        user = get_app_user(verified.subject)
        if user is None:
            raise PermissionDenied(
                "No registry profile is linked to this account. Contact an administrator."
            )

        return user, verified

    def authenticate_header(self, request):
        return self.keyword
