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


def _raise_after_identity_view(request):
    raise RuntimeError("test middleware rollback")


def _write_then_raise_view(request):
    from django.utils import timezone

    from donors.models import Donor

    now = timezone.now()
    Donor.objects.create(
        name="__middleware-rollback-test-donor__",
        blood_type="A+",
        phone="+10000000000",
        created_at=now,
        updated_at=now,
    )
    raise RuntimeError("test write rollback")


def _nested_write_then_raise_view(request):
    from django.db import transaction
    from django.utils import timezone

    from donors.models import Donor

    now = timezone.now()
    with transaction.atomic():
        Donor.objects.create(
            name="__middleware-nested-rollback-donor__",
            blood_type="A+",
            phone="+10000000001",
            created_at=now,
            updated_at=now,
        )
    raise RuntimeError("test nested write rollback")


def _nested_write_then_return_500_view(request):
    from django.db import transaction
    from django.http import HttpResponse
    from django.utils import timezone

    from donors.models import Donor

    now = timezone.now()
    with transaction.atomic():
        Donor.objects.create(
            name="__middleware-nested-500-rollback-donor__",
            blood_type="A+",
            phone="+10000000002",
            created_at=now,
            updated_at=now,
        )
    return HttpResponse("boom", status=500)


urlpatterns = [
    path("__middleware-db-identity__/", _db_identity_view, name="middleware-db-identity"),
    path("__middleware-raise__/", _raise_after_identity_view, name="middleware-raise"),
    path("__middleware-write-raise__/", _write_then_raise_view, name="middleware-write-raise"),
    path(
        "__middleware-nested-write-raise__/",
        _nested_write_then_raise_view,
        name="middleware-nested-write-raise",
    ),
    path(
        "__middleware-nested-write-500__/",
        _nested_write_then_return_500_view,
        name="middleware-nested-write-500",
    ),
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

    def test_identity_context_not_leaked_when_view_raises_after_valid_token(self):
        # Valid token, but the view raises after middleware set transaction-local identity.
        from django.urls import reverse

        with self.assertRaises(RuntimeError):
            self.client.get(reverse("middleware-raise"), **auth_headers(HOSPITAL_ONE_ID))

        # Subsequent unauthenticated request must not see leaked authenticated context.
        probe = self._identity()
        self.assertNotEqual(probe["current_user"], "authenticated")
        self.assertFalse(probe["claim_sub"])
        self.assertFalse(probe["claim_role"])

        # Optional follow-up: a different valid identity should be established cleanly.
        from common.test_helpers import HOSPITAL_TWO_ID

        probe2 = self._identity(**auth_headers(HOSPITAL_TWO_ID))
        self.assertEqual(probe2["current_user"], "authenticated")
        self.assertEqual(probe2["claim_sub"], str(HOSPITAL_TWO_ID))
        self.assertEqual(probe2["claim_role"], "authenticated")

    def test_write_followed_by_exception_is_rolled_back(self):
        # A DB write inside the request that then raises must not be committed (middleware atomic rollback).
        from django.urls import reverse

        from common.test_helpers import ADMIN_ID
        from donors.models import Donor

        with self.assertRaises(RuntimeError):
            self.client.get(reverse("middleware-write-raise"), **auth_headers(ADMIN_ID))

        self.assertFalse(
            Donor.objects.filter(name="__middleware-rollback-test-donor__").exists()
        )

    def test_alternating_hospital_identities_after_failed_request(self):
        from django.urls import reverse

        from common.test_helpers import HOSPITAL_TWO_ID

        with self.assertRaises(RuntimeError):
            self.client.get(reverse("middleware-raise"), **auth_headers(HOSPITAL_ONE_ID))
        probe1 = self._identity()
        self.assertNotEqual(probe1["current_user"], "authenticated")
        self.assertFalse(probe1["claim_sub"])

        probe2 = self._identity(**auth_headers(HOSPITAL_TWO_ID))
        self.assertEqual(probe2["current_user"], "authenticated")
        self.assertEqual(probe2["claim_sub"], str(HOSPITAL_TWO_ID))
        self.assertEqual(probe2["claim_role"], "authenticated")

    def test_nested_atomic_write_followed_by_exception_is_rolled_back(self):
        # View opens a nested transaction.atomic() (savepoint) around a write, then raises.
        # Middleware wraps the request in transaction.atomic() and on Exception sets rollback+re-raises.
        # Expected: the entire middleware request transaction is rolled back, so the nested write is not committed.
        from django.urls import reverse

        from common.test_helpers import ADMIN_ID
        from donors.models import Donor

        with self.assertRaises(RuntimeError):
            self.client.get(reverse("middleware-nested-write-raise"), **auth_headers(ADMIN_ID))

        self.assertFalse(
            Donor.objects.filter(name="__middleware-nested-rollback-donor__").exists()
        )

    def test_nested_atomic_write_followed_by_500_response_is_rolled_back(self):
        # View opens nested transaction.atomic(), writes, exits nested block, then returns HTTP 500 (no exception).
        # Middleware must mark rollback on 5xx and the nested write must not persist.
        from django.urls import reverse

        from common.test_helpers import ADMIN_ID
        from donors.models import Donor

        response = self.client.get(reverse("middleware-nested-write-500"), **auth_headers(ADMIN_ID))
        self.assertEqual(response.status_code, 500)

        self.assertFalse(
            Donor.objects.filter(name="__middleware-nested-500-rollback-donor__").exists()
        )

        # Request-scoped transaction-local identity should be discarded after the request.
        probe = self._identity()
        self.assertNotEqual(probe["current_user"], "authenticated")
        self.assertFalse(probe["claim_sub"])
        self.assertFalse(probe["claim_role"])
