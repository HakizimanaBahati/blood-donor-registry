"""Propagate the verified Supabase identity into the database session.

Supabase RLS helpers read request.jwt.claim.sub. Setting it transaction-locally means
RLS policies can be applied to Django queries as well whenever the configured database
role is subject to RLS (a restricted backend role is recommended in production).
"""
from django.db import connection, transaction

from authentication.jwt import SupabaseTokenError, verify_access_token


class SupabaseClaimsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        verified = None
        header = request.META.get("HTTP_AUTHORIZATION", "")
        if header.lower().startswith("bearer "):
            token = header.split(None, 1)[1].strip()
            try:
                verified = verify_access_token(token)
            except SupabaseTokenError:
                verified = None  # DRF will produce the correct 401 response later
            else:
                request.verified_token = verified

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
            response = self.get_response(request)

        return response
