import time

import jwt
from django.conf import settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from common.test_helpers import ADMIN_ID, HOSPITAL_ONE_ID, auth_headers, make_token


class AuthenticationTests(APITestCase):
    def test_me_returns_resolved_role(self):
        response = self.client.get(reverse("auth-me"), **auth_headers(HOSPITAL_ONE_ID))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["role"], "hospital")
        self.assertIn("hospital_id", response.data)

    def test_missing_token_returns_401(self):
        self.assertEqual(
            self.client.get(reverse("auth-me")).status_code, status.HTTP_401_UNAUTHORIZED
        )

    def test_malformed_authorization_header_returns_401(self):
        response = self.client.get(
            reverse("auth-me"), HTTP_AUTHORIZATION="Token abc.def.ghi"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_expired_token_returns_401(self):
        response = self.client.get(
            reverse("auth-me"), **auth_headers(HOSPITAL_ONE_ID, expires_in=-60)
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_wrong_audience_returns_401(self):
        response = self.client.get(
            reverse("auth-me"), **auth_headers(HOSPITAL_ONE_ID, audience="wrong-app")
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_wrong_secret_returns_401(self):
        response = self.client.get(
            reverse("auth-me"), **auth_headers(HOSPITAL_ONE_ID, secret="not-the-secret")
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unsigned_token_is_rejected(self):
        now = int(time.time())
        payload = {
            "sub": str(HOSPITAL_ONE_ID),
            "aud": settings.SUPABASE_JWT_AUDIENCE,
            "iat": now - 10,
            "exp": now + 300,
        }
        token = jwt.encode(payload, key="", algorithm="none")
        response = self.client.get(reverse("auth-me"), HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_for_unknown_user_returns_403(self):
        response = self.client.get(
            reverse("auth-me"),
            **auth_headers("00000000-0000-4000-8000-000000000000"),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_forged_admin_role_claim_does_not_grant_privileges(self):
        response = self.client.get(
            reverse("hospital-list"),
            **auth_headers(HOSPITAL_ONE_ID, role="admin", app_metadata={"role": "admin"}),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_token_can_access_admin_endpoint(self):
        response = self.client.get(reverse("hospital-list"), **auth_headers(ADMIN_ID))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_logout_returns_explanation(self):
        response = self.client.post(reverse("auth-logout"), **auth_headers(HOSPITAL_ONE_ID))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("signOut", response.data["message"])
