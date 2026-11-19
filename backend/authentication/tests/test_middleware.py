"""Focused tests for SupabaseClaimsMiddleware role activation.

Two clearly distinguished kinds of tests are included:

* ``MiddlewareStatementsTests`` are MOCKED unit tests. No database connection is
  used; they assert the exact SQL statements the middleware emits.
* ``MiddlewareDatabaseTests`` are REAL database tests against the isolated local
  PostgreSQL test cluster (never Supabase). They observe ``current_user`` and the
  claim GUCs through a tiny test-only view.
"""
from unittest.mock import MagicMock, call, patch

from django.db import connection, transaction
from django.http import HttpResponse, JsonResponse
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import path, reverse

from authentication.jwt import SupabaseTokenError, VerifiedToken
from authentication.middleware import SupabaseClaimsMiddleware
from common.test_helpers import HOSPITAL_ONE_ID, auth_headers

SUBJECT = str(HOSPITAL_ONE_ID)


# ── Mocked unit tests (no database) ────────────────────────────────────────────


class _RecordingCursor:
    """Cursor and cursor-context in one; records every execute() call."""

    def __init__(self):
        self.execute = MagicMock()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class MiddlewareStatementsTests(SimpleTestCase):
    """MOCKED: exact SQL statements emitted by the middleware."""

    def _run(self, request, *, verified=None, raises=None):
        cursor = _RecordingCursor()
        response = HttpResponse("ok")
        with patch("authentication.middleware.transaction") as transaction_mock, patch(
            "authentication.middleware.connection"
        ) as connection_mock, patch("authentication.middleware.verify_access_token") as verify:
            connection_mock.cursor.return_value = cursor
            if raises is not None:
                verify.side_effect = raises
            else:
                verify.return_value = verified
            middleware = SupabaseClaimsMiddleware(lambda req: response)
            result = middleware(request)
        return cursor, result, verify

    @staticmethod
    def _request(with_header=True):
        extra = {"HTTP_AUTHORIZATION": "Bearer mocked-token"} if with_header else {}
        return RequestFactory().get("/", **extra)

    def test_valid_token_sets_claims_then_activates_authenticated(self):
        cursor, response, verify = self._run(
            self._request(), verified=VerifiedToken(subject=SUBJECT, claims={})
        )

        self.assertEqual(verify.call_count, 1)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            cursor.execute.call_args_list,
            [
                call(
                    "SELECT set_config('request.jwt.claim.sub', %s, true)",
                    [SUBJECT],
                ),
                call(
                    "SELECT set_config('request.jwt.claim.role', %s, true)",
                    ["authenticated"],
                ),
                call("SET LOCAL ROLE authenticated"),
            ],
        )

    def test_role_switch_is_transaction_local_not_session_level(self):
        cursor, _, _ = self._run(
            self._request(), verified=VerifiedToken(subject=SUBJECT, claims={})
        )
        statements = [c.args[0] for c in cursor.execute.call_args_list]
        self.assertIn("SET LOCAL ROLE authenticated", statements)
        self.assertFalse(
            any(s.strip().upper() == "SET ROLE AUTHENTICATED" for s in statements)
        )
        # Claims must be set transaction-locally (third argument `true`).
        for claim_call in cursor.execute.call_args_list[:2]:
            self.assertTrue(claim_call.args[0].endswith(", true)"))

    def test_invalid_token_does_not_activate_role(self):
        cursor, _, verify = self._run(
            self._request(), raises=SupabaseTokenError("invalid")
        )
        self.assertEqual(verify.call_count, 1)
        cursor.execute.assert_not_called()

    def test_missing_token_does_not_activate_role(self):
        request = self._request(with_header=False)
        cursor, _, verify = self._run(request)
        self.assertEqual(verify.call_count, 0)
        cursor.execute.assert_not_called()
        self.assertFalse(hasattr(request, "verified_token"))


# ── Real database tests (isolated local test cluster only) ─────────────────────


def _db_identity_view(request):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT current_user, "
            "current_setting('request.jwt.claim.sub', true), "
            "current_setting('request.jwt.claim.role', true)"
        )
        current_user, claim_sub, claim_role = cursor.fetchone()
    return JsonResponse(
        {
            "current_user": current_user,
            "claim_sub": claim_sub,
            "claim_role": claim_role,
        }
    )


urlpatterns = [
    path("__middleware-db-identity__/", _db_identity_view, name="middleware-db-identity")
]


@override_settings(
    MIDDLEWARE=["authentication.middleware.SupabaseClaimsMiddleware"],
    ROOT_URLCONF=__name__,
)
class MiddlewareDatabaseTests(TestCase):
    """REAL DB: local isolated test cluster; no Supabase connection is used."""

    def _identity(self, **headers):
        response = self.client.get(reverse("middleware-db-identity"), **headers)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_valid_token_activates_authenticated_with_transaction_local_claims(self):
        data = self._identity(**auth_headers(HOSPITAL_ONE_ID))
        self.assertEqual(data["current_user"], "authenticated")
        self.assertEqual(data["claim_sub"], SUBJECT)
        self.assertEqual(data["claim_role"], "authenticated")

    def test_missing_token_does_not_activate_authenticated(self):
        data = self._identity()
        self.assertNotEqual(data["current_user"], "authenticated")
        self.assertFalse(data["claim_sub"])

    def test_role_and_claims_revert_when_transaction_ends(self):
        with transaction.atomic():
            inside = self._identity(**auth_headers(HOSPITAL_ONE_ID))
            self.assertEqual(inside["current_user"], "authenticated")
            transaction.set_rollback(True)

        outside = self._identity()
        self.assertNotEqual(outside["current_user"], "authenticated")
        self.assertFalse(outside["claim_sub"])
