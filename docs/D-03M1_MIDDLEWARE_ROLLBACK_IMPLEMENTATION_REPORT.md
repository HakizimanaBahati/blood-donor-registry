# D-03M1 — Middleware Transaction Rollback Fix Implementation Report (accurate, D-03M3 updated)

**Date:** 2026-11-23 (original implementation) / 2026-11-23 (D-03M3 corrections)  
**Project:** Blood Donor Registry  
**Branch:** `fix/d-03l-middleware-transaction-rollback` (expected base `6286076`)  
**Scope:** Combined Strategy C in `SupabaseClaimsMiddleware`; middleware regression tests updated/extended; this report corrected to reflect actual changes and test results.

## Files changed (D-03M1 + D-03M3, authorized)

- **Modified:** `backend/authentication/middleware.py` (D-03M1). No changes in D-03M3.
- **Modified:** `backend/authentication/tests/test_middleware.py` (D-03M1 updates + D-03M3 additions: nested write-then-raise view/test, clarifying notes in test context).
- **Modified:** `docs/D-03M1_MIDDLEWARE_ROLLBACK_IMPLEMENTATION_REPORT.md` (D-03M3 rewrite for accuracy).

No other application source, settings, env, migrations, deployment, or configuration files were changed in these steps.

## Implementation summary (`backend/authentication/middleware.py`, `SupabaseClaimsMiddleware.__call__`)

- JWT verified before `transaction.atomic()` via existing `verify_access_token`. On `SupabaseTokenError`, sets `request.verified_token = None`, `request.supabase_auth_error = exc` and continues (no DB identity set).
- Inside `with transaction.atomic():`
  - If verified: sets transaction-local `request.jwt.claim.sub` and `request.jwt.claim.role` (`set_config(..., true)`) and runs `SET LOCAL ROLE authenticated`.
  - **Combined Strategy C:**
    - `try: response = self.get_response(request) except Exception: transaction.set_rollback(True); raise` (catches subclasses of `Exception`; does **not** catch `BaseException`).
    - If response is returned normally, reads `status_code = getattr(response, "status_code", None)`. If `isinstance(status_code, int) and status_code >= 500`, calls `transaction.set_rollback(True)`.
    - Returns the original response unchanged (status/body/headers preserved).
- Policy: 2xx/3xx commit normally (no forced rollback by middleware); **4xx unchanged** (no forced rollback); **5xx (500–599)** → rollback before exit; propagated `Exception` → rollback then re-raise. No explicit `RESET ROLE`/GUC clearing SQL; rollback discards transaction-local state.

## Test changes (`backend/authentication/tests/test_middleware.py`)

- Test URLconf/views (real DB tests): `_db_identity_view`, `_raise_after_identity_view`, `_write_then_raise_view` (creates a `Donor` then raises), and **D-03M3:** `_nested_write_then_raise_view` (opens `transaction.atomic()` nested savepoint, creates a `Donor` named `__middleware-nested-rollback-donor__`, then raises). Routes include `__middleware-nested-write-raise__/`.
- `MiddlewareDatabaseTests` (under `override_settings(MIDDLEWARE=[...], ROOT_URLCONF=__name__)`, `TestCase`):
  - Existing/updated: identity non-leak after raising view with valid token; follow-up identity switch checks.
  - `test_write_followed_by_exception_is_rolled_back`: admin token to `__middleware-write-raise__/` expects `RuntimeError`; asserts no `Donor` named `__middleware-rollback-test-donor__` exists.
  - `test_alternating_hospital_identities_after_failed_request`: after failed raising request with HOSPITAL_ONE, unauth probe shows no authenticated identity; subsequent HOSPITAL_TWO request is authenticated correctly.
  - **D-03M3:** `test_nested_atomic_write_followed_by_exception_is_rolled_back`: admin token to `__middleware-nested-write-raise__/` expects `RuntimeError`; asserts no `Donor` named `__middleware-nested-rollback-donor__` exists.

## Django TestCase outer-transaction behavior (explanation)

Django `TestCase` wraps each test in an outer database transaction that is rolled back at the end of the test. Separately, `SupabaseClaimsMiddleware` opens its own `transaction.atomic()` per request. In these tests, each `self.client` request runs through middleware and thus creates that middleware atomic scope for the request.

**How `test_write_followed_by_exception_is_rolled_back` verifies the middleware transaction boundary (not merely a harness artifact):** the view performs a real ORM insert (`Donor.objects.create(...)`) during the request while the middleware atomic is active (after setting transaction-local role/claims if authenticated), then raises `RuntimeError`. Middleware catches `Exception`, calls `transaction.set_rollback(True)`, and re-raises, so the middleware request transaction is rolled back and that insert is not committed. The test asserts the specific test row is absent after the request completes. This demonstrates rollback of work done in that request path under middleware control; the TestCase outer rollback is separate teardown, but the absence of that named row is the direct effect of middleware-forced rollback on the exception path.

## Nested `transaction.atomic()` behavior (investigation)

**Code path:** Middleware wraps the entire request handling in `with transaction.atomic(): ...` and applies Combined Strategy C (rollback on `Exception`, rollback on HTTP 5xx).

**Django behavior (relevant):** nested `atomic()` uses savepoints in typical cases; calling `transaction.set_rollback(True)` marks rollback for the current atomic context handling so that the wrapped work is not committed successfully on exit in the intended failure mode. With middleware owning the outer request atomic, forcing rollback ensures the request transaction does not commit.

**D-03M3 test:** `test_nested_atomic_write_followed_by_exception_is_rolled_back` — view enters a nested `transaction.atomic()` savepoint, creates `__middleware-nested-rollback-donor__`, exits nested block, then raises. Middleware sets rollback on exception and re-raises; assertion shows the donor row was **not** persisted. This verifies exception-driven rollback still discards writes done inside a nested atomic in the view.

**Not directly tested:** a view that performs writes inside a nested atomic and returns an HTTP 500 response (no exception) while middleware marks rollback due to 5xx. Expected behavior is rollback of the middleware atomic (discarding those writes), but this case was **not automated in D-03M3**.

**Classification:** Nested-atomic **exception** path is **verified by test**; nested-atomic **5xx-return** path is **not directly tested** (documented limitation/expectation only).

## Test execution (permitted; isolated local test DB workflow)

Run from `backend/` with the project virtualenv. Uses repository `manage.py test` / `DomainSchemaTestRunner` conventions (local/`TEST_DATABASE_URL`-driven isolation as configured by the project). No hosted Supabase operations performed.

**After D-03M3:**
- `python manage.py test authentication.tests.test_middleware -v 2` → **OK**: **11 tests**, 0 failures, 0 errors (includes `test_nested_atomic_write_followed_by_exception_is_rolled_back`).
- `python manage.py test authentication.tests.test_rls -v 2` → **OK**: **2 tests**, 0 failures, 0 errors.
- `python manage.py test requests_app.tests.test_api -v 2` → **OK**: **22 tests**, 0 failures, 0 errors.

## Remaining risks and limitations

- Streaming responses: errors after the response object is returned may not be rollback-able by this middleware.
- Only `Exception` subclasses and HTTP 5xx trigger rollback; 4xx returned normally do not (pre-existing writes before a 4xx from app logic are outside this change’s rollback behavior).
- Responses without an integer `status_code >= 500` are not forced to rollback by the 5xx rule.
- Nested atomic **5xx-return** (no exception) path not covered by an automated test.
- Hosted Supabase/RLS/pooler, Render/Vercel, and end-to-end smoke tests remain out of scope.

## D-03M1 readiness for commit (D-03M3 assessment)

- D-03M2 gaps addressed in this report: TestCase outer-transaction explanation, write-rollback rationale, nested-atomic investigation, added nested exception-path test and results.
- Authorized changes only: `backend/authentication/middleware.py` unchanged in D-03M3; `backend/authentication/tests/test_middleware.py` and this report updated.
- Relevant suites pass locally (11/2/22 as above).

**Readiness:** **Conditionally ready** for committing the authorized file set, if the team accepts documented limitations (especially untested nested-atomic **5xx-return** path and existing streaming/4xx notes). If a hard requirement is automated coverage of nested-atomic followed by a 5xx response causing rollback, that is still missing and should be added or explicitly waived.