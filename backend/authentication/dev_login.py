"""Development-only login helper for classroom demos without a Supabase project.

This view is disabled unless DJANGO_DEBUG=true. It issues a locally signed token for
the seeded fictional profiles so the full browser → Django → database flow can be
demonstrated offline. It is NOT a production authentication mechanism.
"""
import time

import jwt
from django.conf import settings
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

DEV_USERS = {
    "admin": ("b0000000-0000-4000-8000-000000000001", "admin"),
    "hospital1": ("b0000000-0000-4000-8000-000000000002", "hospital"),
    "hospital2": ("b0000000-0000-4000-8000-000000000003", "hospital"),
}


class DevLoginView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        if not settings.DEBUG:
            raise PermissionDenied("Development login is disabled in production.")
        key = request.data.get("user")
        if key not in DEV_USERS:
            raise ValidationError({"user": "Choose admin, hospital1 or hospital2."})
        user_id, role = DEV_USERS[key]
        now = int(time.time())
        claims = {
            "sub": user_id,
            "aud": settings.SUPABASE_JWT_AUDIENCE,
            "iat": now - 10,
            "exp": now + 3600,
            "role": "authenticated",
        }
        if settings.SUPABASE_JWT_ISSUER:
            claims["iss"] = settings.SUPABASE_JWT_ISSUER
        token = jwt.encode(claims, settings.SUPABASE_JWT_SECRET, algorithm="HS256")
        return Response({"access_token": token, "role": role, "user_id": user_id})
