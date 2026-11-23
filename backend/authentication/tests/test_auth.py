import base64
import json
import time
from unittest.mock import patch

import jwt
from django.conf import settings
from django.test import SimpleTestCase, override_settings
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

    def test_untrusted_algorithm_header_cannot_inject_log_lines(self):
        def b64url(value: dict) -> str:
            return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=").decode()

        malicious_algorithm = "HS256\nINJECTED-LOG-LINE"
        token = (
            f"{b64url({'alg': malicious_algorithm, 'typ': 'JWT'})}."
            f"{b64url({})}.c2lnbmF0dXJl"
        )
        with self.assertLogs("authentication.jwt", level="WARNING") as logs:
            response = self.client.get(
                reverse("auth-me"), HTTP_AUTHORIZATION=f"Bearer {token}"
            )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        rendered = "\n".join(record.getMessage() for record in logs.records)
        self.assertNotIn("\nINJECTED-LOG-LINE", rendered)
        self.assertIn("algorithm=HS256 INJECTED-LOG-LINE", rendered)
        record = next(
            record
            for record in logs.records
            if "Supabase JWT verification failed" in record.getMessage()
        )
        self.assertEqual(
            getattr(record, "jwt_algorithm", None), "HS256 INJECTED-LOG-LINE"
        )

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
        self.assertNotIn("Bearer ", joined)
        failure_records = [r for r in logs.records if "Supabase JWT verification failed" in r.getMessage()]
        self.assertTrue(failure_records)
        for record in failure_records:
            message = record.getMessage()
            self.assertIn("category=expired", message)
            self.assertIn("algorithm=ES256", message)
            self.assertIn("kid_present=True", message)
            self.assertIn("jwt_error_class=ExpiredSignatureError", message)
            self.assertIn("jwt_jwks_host=", message)
            self.assertEqual(getattr(record, "jwt_failure_category", None), "expired")
            self.assertEqual(getattr(record, "jwt_algorithm", None), "ES256")
            self.assertEqual(getattr(record, "jwt_kid_present", None), True)
            self.assertEqual(getattr(record, "jwt_error_class", None), "ExpiredSignatureError")
            self.assertIn("jwt_jwks_host", record.__dict__)
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

    def _failure_logs(self, logs):
        return [r for r in logs.records if "Supabase JWT verification failed" in r.getMessage()]

    def test_type_error_is_classified_as_unexpected_type_error(self):
        exc = TypeError("unsupported operand type(s) for verification: safe detail")
        token = make_es256_token(HOSPITAL_ONE_ID, private_key=self.private_key)
        with self._mock_jwk_client(exc=exc):
            with self.assertLogs("authentication.jwt", level="WARNING") as logs:
                response = self.client.get(reverse("auth-me"), HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        failure_logs = self._failure_logs(logs)
        self.assertEqual(len(failure_logs), 1)
        record = failure_logs[0]
        self.assertEqual(getattr(record, "jwt_failure_category", None), "unexpected_type_error")
        self.assertIn("category=unexpected_type_error", record.getMessage())
        self.assertEqual(getattr(record, "jwt_error_class", None), "TypeError")
        self.assertEqual(
            getattr(record, "jwt_error_message", None),
            "unsupported operand type(s) for verification: safe detail",
        )
        self.assertIn(
            "jwt_error_message=unsupported operand type(s) for verification: safe detail",
            record.getMessage(),
        )

    def test_non_type_jwks_error_keeps_jwks_retrieval_category_and_logs_safe_message(self):
        token = make_es256_token(HOSPITAL_ONE_ID, private_key=self.private_key)
        with self._mock_jwk_client(exc=RuntimeError("jwks endpoint returned 503")):
            with self.assertLogs("authentication.jwt", level="WARNING") as logs:
                response = self.client.get(reverse("auth-me"), HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        failure_logs = self._failure_logs(logs)
        self.assertEqual(len(failure_logs), 1)
        record = failure_logs[0]
        self.assertEqual(getattr(record, "jwt_failure_category", None), "jwks_retrieval")
        self.assertEqual(getattr(record, "jwt_error_class", None), "RuntimeError")
        self.assertEqual(getattr(record, "jwt_error_message", None), "jwks endpoint returned 503")
        self.assertIn("jwt_error_message=jwks endpoint returned 503", record.getMessage())

    def test_sensitive_values_are_redacted_from_verification_logs(self):
        token = make_es256_token(HOSPITAL_ONE_ID, private_key=self.private_key)
        fake_api_key = "sk_live_abcdef1234567890"
        fake_password = "hunter2-do-not-log"
        fake_email = "private-user@example.invalid"
        exc = TypeError(
            f"bad Authorization: Bearer {token}; jwt={token}; "
            f"api_key={fake_api_key}; password={fake_password}; email={fake_email}; safe detail"
        )
        with self._mock_jwk_client(exc=exc):
            with self.assertLogs("authentication.jwt", level="WARNING") as logs:
                response = self.client.get(reverse("auth-me"), HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        failure_logs = self._failure_logs(logs)
        self.assertTrue(failure_logs)
        rendered = "\n".join(r.getMessage() for r in failure_logs)
        structured = "\n".join(str(getattr(r, "jwt_error_message", "")) for r in failure_logs)
        for sensitive in (
            token,
            f"Bearer {token}",
            "Bearer ",
            fake_api_key,
            fake_password,
            fake_email,
        ):
            self.assertNotIn(sensitive, rendered)
            self.assertNotIn(sensitive, structured)
        self.assertIn("jwt_error_message=", rendered)
        self.assertIn("[REDACTED]", rendered)

    def test_environment_secret_is_not_logged_without_an_explicit_label(self):
        fake_env_secret = "fake-env-secret-9f8e7d6c5b4a"
        token = make_es256_token(HOSPITAL_ONE_ID, private_key=self.private_key)
        exc = TypeError(f"internal detail {fake_env_secret} after token check")
        with override_settings(SUPABASE_JWT_SECRET=fake_env_secret):
            with self._mock_jwk_client(exc=exc):
                with self.assertLogs("authentication.jwt", level="WARNING") as logs:
                    response = self.client.get(reverse("auth-me"), HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        failure_logs = self._failure_logs(logs)
        self.assertTrue(failure_logs)
        rendered = "\n".join(r.getMessage() for r in failure_logs)
        structured = "\n".join(str(getattr(r, "jwt_error_message", "")) for r in failure_logs)
        self.assertNotIn(fake_env_secret, rendered)
        self.assertNotIn(fake_env_secret, structured)

    def test_sanitized_error_message_is_limited_to_200_characters(self):
        token = make_es256_token(HOSPITAL_ONE_ID, private_key=self.private_key)
        exc = RuntimeError("safe diagnostic detail " * 20)
        with self._mock_jwk_client(exc=exc):
            with self.assertLogs("authentication.jwt", level="WARNING") as logs:
                response = self.client.get(reverse("auth-me"), HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        failure_logs = self._failure_logs(logs)
        self.assertTrue(failure_logs)
        for record in failure_logs:
            message = getattr(record, "jwt_error_message", "")
            self.assertLessEqual(len(message), 200)
            self.assertTrue(message.endswith("..."))


class JWKClientFactoryTests(SimpleTestCase):
    """Exercise the real factory; PyJWKClient construction performs no network I/O."""

    def setUp(self):
        import authentication.jwt as auth_jwt

        self._cached_instance = auth_jwt._jwk_client_instance
        self._cached_url = auth_jwt._jwk_client_url
        auth_jwt._jwk_client_instance = None
        auth_jwt._jwk_client_url = None

    def tearDown(self):
        import authentication.jwt as auth_jwt

        auth_jwt._jwk_client_instance = self._cached_instance
        auth_jwt._jwk_client_url = self._cached_url
        super().tearDown()

    def test_repeated_calls_return_same_cached_instance_and_factory_stays_callable(self):
        import authentication.jwt as auth_jwt

        with override_settings(SUPABASE_JWKS_URL="https://jwks-one.example.invalid/jwks.json"):
            first = auth_jwt._jwk_client()
            self.assertTrue(callable(auth_jwt._jwk_client))
            second = auth_jwt._jwk_client()
        self.assertIsInstance(first, jwt.PyJWKClient)
        self.assertIs(first, second)
        self.assertTrue(callable(auth_jwt._jwk_client))

    def test_changing_jwks_url_creates_new_client(self):
        import authentication.jwt as auth_jwt

        with override_settings(SUPABASE_JWKS_URL="https://jwks-one.example.invalid/jwks.json"):
            first = auth_jwt._jwk_client()
        with override_settings(SUPABASE_JWKS_URL="https://jwks-two.example.invalid/jwks.json"):
            second = auth_jwt._jwk_client()
            third = auth_jwt._jwk_client()
        self.assertIsNot(first, second)
        self.assertIs(second, third)
        self.assertEqual(auth_jwt._jwk_client_url, "https://jwks-two.example.invalid/jwks.json")
