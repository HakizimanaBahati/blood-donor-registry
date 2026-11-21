import time
from unittest.mock import patch

import jwt
from django.conf import settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from common.test_helpers import (
    ADMIN_ID,
    ES256_TEST_KID,
    HOSPITAL_ONE_ID,
    MockJWKClient,
    auth_headers,
    es256_auth_headers,
    generate_es256_keypair,
    make_es256_token,
    make_token,
)


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


class ES256AuthenticationTests(APITestCase):
    def setUp(self):
        import authentication.jwt as auth_jwt

        self.private_key, self.public_key = generate_es256_keypair()
        self._jwks_client = auth_jwt._jwk_client
        self._jwks_client_url = auth_jwt._jwk_client_url
        auth_jwt._jwk_client = None
        auth_jwt._jwk_client_url = None

    def tearDown(self):
        import authentication.jwt as auth_jwt

        auth_jwt._jwk_client = self._jwks_client
        auth_jwt._jwk_client_url = self._jwks_client_url
        super().tearDown()

    def _mock_jwk_client(self, *, key=None, exc=None):
        client = MockJWKClient(key=self.public_key if key is None else key, exc=exc)
        return patch("authentication.jwt._jwk_client", return_value=client)

    def test_valid_es256_token_with_known_kid_authenticates_admin(self):
        with self._mock_jwk_client():
            response = self.client.get(
                reverse("auth-me"),
                **es256_auth_headers(ADMIN_ID, private_key=self.private_key),
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["role"], "admin")

    def test_valid_es256_token_with_known_kid_authenticates_hospital(self):
        with self._mock_jwk_client():
            response = self.client.get(
                reverse("auth-me"),
                **es256_auth_headers(HOSPITAL_ONE_ID, private_key=self.private_key),
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["role"], "hospital")
        self.assertIn("hospital_id", response.data)

    def test_tampered_es256_signature_is_rejected(self):
        token = make_es256_token(HOSPITAL_ONE_ID, private_key=self.private_key)
        header, payload, signature = token.split(".")
        tampered_signature = ("A" if signature[0] != "A" else "B") + signature[1:]
        tampered = f"{header}.{payload}.{tampered_signature}"
        with self._mock_jwk_client():
            response = self.client.get(reverse("auth-me"), HTTP_AUTHORIZATION=f"Bearer {tampered}")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["error"]["code"], "authentication_failed")
        self.assertIsNone(response.data["error"]["details"])

    def test_expired_es256_token_is_rejected(self):
        with self._mock_jwk_client():
            response = self.client.get(
                reverse("auth-me"),
                **es256_auth_headers(HOSPITAL_ONE_ID, private_key=self.private_key, expires_in=-60),
            )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_es256_token_with_wrong_issuer_is_rejected(self):
        with self._mock_jwk_client():
            response = self.client.get(
                reverse("auth-me"),
                **es256_auth_headers(
                    HOSPITAL_ONE_ID,
                    private_key=self.private_key,
                    issuer="https://wrong-issuer.example.invalid/auth/v1",
                ),
            )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_es256_token_with_wrong_audience_is_rejected(self):
        with self._mock_jwk_client():
            response = self.client.get(
                reverse("auth-me"),
                **es256_auth_headers(HOSPITAL_ONE_ID, private_key=self.private_key, audience="wrong-aud"),
            )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unknown_kid_after_jwks_refresh_is_rejected(self):
        exc = jwt.exceptions.PyJWKClientError("Unable to find a signing key that matches: unknown-kid")
        with self._mock_jwk_client(exc=exc):
            response = self.client.get(
                reverse("auth-me"),
                **es256_auth_headers(HOSPITAL_ONE_ID, private_key=self.private_key, kid="unknown-kid"),
            )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["error"]["code"], "authentication_failed")

    def test_jwks_endpoint_unavailable_is_rejected(self):
        with self._mock_jwk_client(exc=RuntimeError("jwks unavailable")):
            response = self.client.get(
                reverse("auth-me"),
                **es256_auth_headers(HOSPITAL_ONE_ID, private_key=self.private_key),
            )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["error"]["code"], "authentication_failed")

    def test_es256_token_missing_sub_is_rejected(self):
        with self._mock_jwk_client():
            token = make_es256_token(HOSPITAL_ONE_ID, private_key=self.private_key)
            # Build a token without sub by encoding manually.
            now = int(time.time())
            claims = {
                "aud": settings.SUPABASE_JWT_AUDIENCE,
                "iat": now - 10,
                "exp": now + 3600,
                "role": "authenticated",
            }
            if settings.SUPABASE_JWT_ISSUER:
                claims["iss"] = settings.SUPABASE_JWT_ISSUER
            token = jwt.encode(claims, self.private_key, algorithm="ES256", headers={"kid": ES256_TEST_KID})
            response = self.client.get(reverse("auth-me"), HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_es256_token_non_uuid_sub_is_rejected(self):
        with self._mock_jwk_client():
            now = int(time.time())
            claims = {
                "sub": "not-a-uuid",
                "aud": settings.SUPABASE_JWT_AUDIENCE,
                "iat": now - 10,
                "exp": now + 3600,
                "role": "authenticated",
            }
            if settings.SUPABASE_JWT_ISSUER:
                claims["iss"] = settings.SUPABASE_JWT_ISSUER
            token = jwt.encode(claims, self.private_key, algorithm="ES256", headers={"kid": ES256_TEST_KID})
            response = self.client.get(reverse("auth-me"), HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_alg_none_token_is_rejected(self):
        now = int(time.time())
        claims = {
            "sub": str(HOSPITAL_ONE_ID),
            "aud": settings.SUPABASE_JWT_AUDIENCE,
            "iat": now - 10,
            "exp": now + 3600,
        }
        if settings.SUPABASE_JWT_ISSUER:
            claims["iss"] = settings.SUPABASE_JWT_ISSUER
        token = jwt.encode(claims, key="", algorithm="none")
        response = self.client.get(reverse("auth-me"), HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unsupported_algorithm_is_rejected(self):
        # HS512 is not in JWT_ALGORITHMS; verification must fail closed.
        token = make_token(HOSPITAL_ONE_ID, algorithm="HS512")
        response = self.client.get(reverse("auth-me"), HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_forged_role_claim_does_not_override_profile_role_es256(self):
        with self._mock_jwk_client():
            response = self.client.get(
                reverse("hospital-list"),
                **es256_auth_headers(
                    HOSPITAL_ONE_ID,
                    private_key=self.private_key,
                    role="admin",
                    app_metadata={"role": "admin"},
                ),
            )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_es256_verification_failure_is_logged_without_token(self):
        token = make_es256_token(HOSPITAL_ONE_ID, private_key=self.private_key, expires_in=-60)
        with self._mock_jwk_client():
            with self.assertLogs("authentication.jwt", level="WARNING") as logs:
                response = self.client.get(reverse("auth-me"), HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        joined = "\n".join(logs.output)
        self.assertNotIn(token, joined)
        self.assertTrue(any(getattr(r, "jwt_failure_category", None) == "expired" for r in logs.records))
        self.assertTrue(any(getattr(r, "jwt_algorithm", None) == "ES256" for r in logs.records))
        self.assertTrue(any(getattr(r, "jwt_kid_present", None) is True for r in logs.records))
        self.assertTrue(all(getattr(r, "jwt_error_class", None) for r in logs.records))

    def test_invalid_es256_token_is_logged_once_across_middleware_and_drf(self):
        token = make_es256_token(HOSPITAL_ONE_ID, private_key=self.private_key, audience="wrong-aud")
        with self._mock_jwk_client():
            with self.assertLogs("authentication.jwt", level="WARNING") as logs:
                response = self.client.get(reverse("auth-me"), HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        failure_logs = [r for r in logs.records if "Supabase JWT verification failed" in r.getMessage()]
        self.assertEqual(len(failure_logs), 1)
