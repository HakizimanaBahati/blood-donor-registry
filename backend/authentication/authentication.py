from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied

from authentication.jwt import SupabaseTokenError, verify_access_token
from authentication.services import get_app_user


class SupabaseJWTAuthentication(BaseAuthentication):
    """Authenticate a Supabase-issued bearer token and resolve the local app role."""

    keyword = "Bearer"

    def authenticate(self, request):
        header = get_authorization_header(request)
        if not header:
            return None

        parts = header.split()
        if len(parts) != 2 or parts[0].decode("ascii", "ignore").lower() != self.keyword.lower():
            raise AuthenticationFailed("Authorization header must use the Bearer scheme.")

        try:
            token = parts[1].decode("ascii")
        except UnicodeDecodeError as exc:
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
