# D-03H — Exception Path & Identity Rollback Audit (Read-Only)

Date: 2026-11-23  
Project: Blood Donor Registry  
Scope: Read-only inspection of `SupabaseClaimsMiddleware`, JWT/auth integration, middleware/RLS tests, and transaction behavior relevant to exception handling after setting transaction-local DB identity context. No hosted DB access, no SQL executed, no code/test/settings/migrations/env/infrastructure changes, no `b05b7_r.py` execution, no git state changes.  
Inputs: `docs/D-03G_TRANSACTION_IDENTITY_ISOLATION_AUDIT.md`, `docs/D-03D_DATABASE_CONNECTION_SECURITY_AUDIT.md`, `docs/D-03F_DATABASE_SECURITY_REMEDIATION_PLAN.md`, and repository files listed below.

## 1. Files inspected (read-only)

- `backend/authentication/middleware.py` (`SupabaseClaimsMiddleware`)
- `backend/authentication/jwt.py` (`verify_access_token`, `SupabaseTokenError`, sanitization/logging)
- `backend/authentication/authentication.py` (`SupabaseJWTAuthentication`)
- `backend/authentication/permissions.py` (context)
- `backend/config/settings.py` (MIDDLEWARE order, `DATABASES`, `ATOMIC_REQUESTS` absent, middleware list)
- `backend/authentication/tests/test_middleware.py` (mocked + real DB tests, including rollback-related test)
- `backend/authentication/tests/test_rls.py` (manual role/GUC setup patterns)
- `backend/common/test_helpers.py` (token/header helpers, test UUIDs)
- `backend/requests_app/tests/test_api.py` (spot-checked for context; no exception-in-middleware identity rollback tests observed)

## 2. Trace of the exception path through `transaction.atomic()` (source evidence)

**Implementation (`backend/authentication/middleware.py`):**
```text
SupabaseClaimsMiddleware.__call__(request):
  - set request.auth_debug_request_id, log
  - if Authorization: Bearer ...: verify_access_token(token)
      on SupabaseTokenError: set verified=None, request.supabase_auth_error = exc
      on success: set request.verified_token = verified, clear supabase_auth_error
  - with transaction.atomic():
      if verified:
          cursor: set_config('request.jwt.claim.sub', verified.subject, true)
          cursor: set_config('request.jwt.claim.role', 'authenticated', true)
          cursor: SET LOCAL ROLE authenticated
      response = self.get_response(request)
  - return response
```

**Key points (from code):**
- JWT verification (`verify_access_token`) runs **before** entering `transaction.atomic()`. Therefore, a JWT parsing/verification error does **not** create the middleware’s DB transaction context with identity set by that successful-verified branch except in the normal success path; on verification failure the code sets `request.supabase_auth_error` and proceeds into `transaction.atomic()` **without** executing the role/GUC SQL.
- The middleware opens a **single** `transaction.atomic()` block for the entire request handling of `get_response(request)`. There is **no** `try/except` around `get_response` inside the middleware: if `get_response` raises any exception, the exception propagates out of the `with transaction.atomic():` context. Django’s `atomic` context manager will, by default, mark the transaction for rollback on exception (standard Django behavior) unless handled by nested savepoints in a specific way that is not present here.
- The DB session statements that establish identity context (`set_config(..., true)`, `SET LOCAL ROLE authenticated`) are executed **inside** that same `transaction.atomic()` block **before** calling `get_response`. They are transaction-scoped in PostgreSQL terms (`set_config` called with `is_local=true`, `SET LOCAL ROLE` is transaction-scoped in effect for the transaction). When the transaction rolls back, those session-local changes made within the transaction are discarded.
- No global `ATOMIC_REQUESTS=True` is set in `backend/config/settings.py`; the only request-wrapping atomic behavior for this identity path is this middleware’s explicit `transaction.atomic()`.
- `SupabaseJWTAuthentication` may run later (DRF) and can raise `AuthenticationFailed`/`PermissionDenied`; those are Python exceptions raised during view/authentication/permission phases (i.e. inside `get_response`). Such exceptions will cause the middleware’s `atomic` block to unwind with an exception, leading to rollback of the transaction that was opened in middleware (including any identity GUCs/role set inside it), assuming no outer transaction swallows/commits in an unexpected way. **This is the expected rollback path by structure**, but is **not directly asserted by an automated test** in the repo (see §3).

**Conclusion (source):** The code structure is consistent with: **if an exception is raised after `verified` is True and after the three DB statements ran (or during `get_response`), the surrounding `transaction.atomic()` will roll back, removing transaction-local role/GUC changes set inside that transaction.** This is a **design/structural inference** supported by Django’s `atomic` semantics; it is **not independently proven** here by a dedicated failing-view test that inspects DB state post-rollback.

## 3. Existing tests for exception-after-identity-context behavior

### 3.1 `backend/authentication/tests/test_middleware.py`
- **`MiddlewareStatementsTests` (mocked, `SimpleTestCase`):** patches `transaction.atomic` context manager behavior indirectly via mocks? It patches `authentication.middleware.transaction` and `authentication.middleware.connection` and `authentication.middleware.verify_access_token`. It verifies SQL call order and that no executes occur on missing/invalid token. It does **not** test a case where `get_response` raises an exception after identity SQL is executed.
- **`MiddlewareDatabaseTests` (real DB, local isolated test cluster):**
  - `test_valid_token_activates_authenticated_with_transaction_local_claims`: confirms identity view sees authenticated/claims for a successful request.
  - `test_missing_token_does_not_activate_authenticated`: confirms no activation.
  - `test_role_and_claims_revert_when_transaction_ends`: uses `transaction.atomic()` in the **test** and sets `transaction.set_rollback(True)` after calling `self.client.get(...)` (so the test forces rollback of the test’s outer transaction context around that request call in that test pattern). It then checks a subsequent request sees no authenticated context. This demonstrates **reversion after rollback/end of that scoped transaction context in the test**, but it is **not** the same as “the middleware’s own `atomic` rolled back because `get_response` raised”. It is indirect evidence of transaction-local scoping, not a direct exception-propagation test of the middleware path.

**No test found** that: (a) uses a view that raises after middleware has set identity, (b) asserts the exception is propagated, and (c) asserts a following request (or a probe) does not inherit the prior identity/GUCs/role state from that failed transaction.

### 3.2 `backend/authentication/tests/test_rls.py`
- Manually sets `SET LOCAL ROLE authenticated` and claim GUCs inside test-controlled transactions and asserts DB behavior/errors. No middleware exception-path test. Finally blocks reset state for test hygiene—**not** equivalent to middleware rollback-on-exception behavior.

### 3.3 Other tests
- `backend/requests_app/tests/test_api.py` covers API behavior (401s, scoping) but does not inject a view exception to validate middleware transaction rollback of identity context. No other middleware exception rollback test observed in inspected test files.

**Summary:** **No existing automated test covers the specific case “verified JWT → middleware sets transaction-local identity/role inside `transaction.atomic()` → `get_response` raises → transaction rolled back → subsequent request has no leaked authenticated context / GUCs.”**

## 4. Could a subsequent request inherit the previous request’s identity?

### 4.1 Source-based answer
- **Within the same failed request’s transaction:** any DB work done inside the middleware’s `atomic` block before the exception would be rolled back; transaction-local `set_config(..., true)` and `SET LOCAL ROLE` are scoped to that transaction and are not committed. So the failed request should not leave committed identity state in that transaction.
- **Across different requests (normal case):** each request goes through `SupabaseClaimsMiddleware` again, opens a new `transaction.atomic()` (middleware does this unconditionally), and sets context only if it verifies a Bearer token for that request. With `DATABASES["default"]["OPTIONS"]` default and `conn_max_age=0` in `settings.py`, Django does not keep persistent connections across requests by `CONN_MAX_AGE` pooling; this reduces the chance of reusing a server connection that still had session-level leftovers. However, **external connection pooling (Supabase poolers/PgBouncer/Supavisor)** is **not configured in repo** and behavior is **deployment-dependent** (see §6 / D-03D/D-03F). In some pooler modes, server connections may be reassigned in ways that interact badly with role/GUC assumptions, but transaction-local settings set inside a committed/rolled-back transaction should not persist on the server connection after the transaction ends in normal Postgres behavior—**pooler behavior can differ**.
- **Risk (unverified):** if a pooler or an unusual connection reuse pattern caused the same server session to be handed to another client request with stale session state, or if code executed outside the middleware transaction in a misconfigured environment, inheritance/leakage is possible in principle. **No source evidence of such a path in the inspected request flow**, but **not proven absent** by tests under pooled conditions.

### 4.2 Test-based answer
- `MiddlewareDatabaseTests.test_role_and_claims_revert_when_transaction_ends` shows that after the test-induced rollback/scoped transaction end, a subsequent request sees `current_user != "authenticated"` and falsy claim values (in that test setup). This is **evidence in the local isolated test DB** that context does not persist across that boundary in that test, but it does **not** test the “view raised exception” path and does **not** test external pooling.

**Classification for “could inherit…”:** **NOT VERIFIED** as a general guarantee in all deployed (especially pooled) environments; **source structure suggests rollback prevents persistence in the middleware transaction**, and **one local test suggests non-persistence in a related rollback scenario**, but no direct exception-path test exists.

## 5. Can the current test suite verify this safely using the isolated local PostgreSQL database on port `55432`?

**Yes, in principle, with additions—under the existing test infrastructure assumptions.**

Evidence from repo:
- `backend/config/test_runner.py` overrides the test DB from `TEST_DATABASE_URL` when set (and is used by `TEST_RUNNER = "config.test_runner.DomainSchemaTestRunner"` in settings). It applies local Supabase emulation/migrations for tests. The suite is designed to run against an **isolated local** PostgreSQL cluster (per comments in test runner and middleware test docstrings). D-02H notes verification used an isolated local loopback Postgres on port `55432` via `TEST_DATABASE_URL` in that context—**this matches the “port 55432” mentioned in the task**.
- `MiddlewareDatabaseTests` already proves the test harness can: (a) run Django tests with middleware active, (b) issue requests via `self.client`, (c) hit a test view that inspects `current_user` and `request.jwt.claim.*` via SQL on the default DB connection, (d) assert identity context in a real local test DB.
- A safe verification approach (conceptual, no implementation): add a test view that, when called with a specific trigger (e.g. query param/header set in test only), raises an exception **after** middleware has already set identity for a verified request? But the middleware sets identity inside its own `transaction.atomic()` and then calls `get_response`; if the view raises, the exception bubbles out through `atomic` — so the rollback happens at the middleware boundary. To test this end-to-end you could: (1) add a temporary test URL/view (test-only URLconf override, as `MiddlewareDatabaseTests` does) that raises `RuntimeError` (or similar) for a flagged request, (2) send a request with a valid Bearer token to that view and assert the request results in a 500/error response, (3) send a second request to the `__middleware-db-identity__` probe (or equivalent) with **no token** and assert no authenticated context / empty claims (proving no leakage from the failed request). This uses the **same isolated local test DB** and the **same middleware stack** pattern already used in tests. No hosted DB involved.

**Caveats:**
- The test must be careful about transaction nesting/behavior in the test client and the middleware’s `atomic`. In practice, this is feasible but should be written carefully (e.g. avoid wrapping the test client call in an outer `transaction.atomic()` that would change rollback semantics unexpectedly, unlike `test_role_and_claims_revert_when_transaction_ends` which did that intentionally).
- This is a **test addition** (code change) and is **not performed here** (read-only audit). The question asks “Check whether the current test suite can verify this safely…” — answer is **YES, it can be added/verified safely using the existing isolated local PostgreSQL test setup** (e.g. port 55432 via `TEST_DATABASE_URL`), provided tests follow the existing patterns and do not touch hosted DB.

## 6. Identified missing regression tests (exact list)

1. **Exception after identity context set (middleware transaction rollback, end-to-end HTTP):** A test that sends a request with a valid `Authorization: Bearer ...` to an endpoint/view that raises after (or during) handler execution while middleware has set `request.jwt.claim.sub`, `request.jwt.claim.role='authenticated'`, and `SET LOCAL ROLE authenticated` inside `transaction.atomic()`. Assert: (a) the request fails (e.g. 500) as expected, (b) a subsequent request with **no** token to a probe view shows no authenticated DB role and empty/falsey claim GUCs (no identity leakage from the failed transaction). This is the primary missing test for P2-R.
2. **Exception after identity context set (assertion of non-leakage across different identity):** After the above failure with identity A, send a request with identity B’s valid token and assert identity B is correctly established (no contamination from the failed A attempt). (Stronger regression guard.)
3. **Exception raised from DRF authentication/permission layer in a path that still went through middleware’s verified-token + context-setting branch:** Verify rollback behavior when the failure occurs after middleware set DB context but inside DRF auth/permission raising (e.g. `PermissionDenied` from `get_app_user` returning None in an edge case) — complements the view-exception case.
4. **(Optional, lower priority) Nested transaction/savepoint note:** Document/test note that if application code uses savepoints in unexpected ways, rollback semantics could differ; current middleware design uses a single outer `atomic` per request — consider adding a comment/test note only if behavior is observed in practice. Not strictly required if no such code exists.
5. **(Staging, not unit-testable in same way):** Pooler-mode tests for identity non-leakage across requests under real Supabase poolers (transaction/session) as described in D-03F Q8 — these are operational validation, not unit tests, but are the missing “runtime proof” counterpart.

## 7. Exact next test needed (recommended, for implementation later with approval)

**Recommended test name (example):** `test_identity_context_not_leaked_when_view_raises_after_valid_token` (in `backend/authentication/tests/test_middleware.py`, under a real-DB test class using the same pattern as `MiddlewareDatabaseTests`).

**Setup (test-only):**
- Extend the test `ROOT_URLCONF` used by `MiddlewareDatabaseTests` (or add a new test URLconf) to include a route that raises, e.g. `path("__middleware-raise__", _raise_view, name="middleware-raise")` where `_raise_view(request): raise RuntimeError("test middleware rollback")`.
- Keep `MIDDLEWARE = ["authentication.middleware.SupabaseClaimsMiddleware"]` (as in existing test) so middleware behavior is exercised.

**Steps:**
1. `response = self.client.get(reverse("middleware-raise"), **auth_headers(HOSPITAL_ONE_ID))` (use a valid token for an existing test profile context as in `auth_headers`/fixtures used by the test DB setup).
2. Assert the response indicates server error (e.g. `response.status_code == 500` in default DEBUG/handler behavior for unhandled exceptions in tests, depending on test client settings) — **do not** assert internal details.
3. `probe = self.client.get(reverse("middleware-db-identity"))` (no token).
4. Assert `probe.status_code == 200` and JSON shows no authenticated activation: `current_user != "authenticated"` (or equals the DB login role default in that context) and `claim_sub` falsy/empty and `claim_role` falsy/empty (matching existing `test_missing_token_does_not_activate_authenticated` expectations).

**Optional stronger follow-up in same test or separate test:**
5. Call `self.client.get(reverse("middleware-db-identity"), **auth_headers(ANOTHER_VALID_ID))` and assert the identity for that second request is correct for the new token (no residue from the failed first request).

**Why this is the exact next test:** It directly validates the reported risk (“request receives verified JWT, sets transaction-local identity claims, switches to `authenticated`, and then raises an exception reliably rolls back…” and “subsequent request could inherit…”). It uses the existing isolated local PostgreSQL test DB path (`DomainSchemaTestRunner`/`TEST_DATABASE_URL`-style local setup) and the existing probe pattern already proven in `MiddlewareDatabaseTests`, so it is low-risk to add and high-value for regression protection.

**Constraints reminder:** implementing this test requires code/test changes (new test view in test module + test method). That is **not done in this audit** (read-only). Any implementation must be done only with explicit approval and must not touch hosted DB or production code behavior except tests.

## 8. Classification

**Overall classification for this audit topic: FAIL (for “verified by automated test”) / NOT VERIFIED (for runtime/pooler guarantee) — reported as:**  
**PASS (source structure) with a concrete FAILING GAP in automated test coverage for the exception-after-identity path.**

More precisely:
- **Source-code/structural assessment (exception path through `transaction.atomic()`):** **PASS (by design).** Middleware sets identity only inside a request-wrapping `transaction.atomic()` after successful verification and before calling `get_response`; on exception, the transaction is rolled back by Django’s atomic behavior, so transaction-local role/GUC changes should not persist. This is consistent and clear in code.
- **Automated test coverage of that exact path:** **FAIL (missing).** No test forces `get_response` to raise after verified identity was set and asserts rollback/non-leakage to a subsequent request. The existing rollback test is indirect (test-forced rollback around the request call), not the same scenario.
- **Runtime guarantee across deployed environments (especially external poolers):** **NOT VERIFIED.** No evidence in repo/tests for pooler behavior; could, in misconfigured pooling, behave unexpectedly (see D-03D/D-03F). Requires staging validation.

**Final label for this deliverable (choose one):** **NOT VERIFIED** as fully proven end-to-end in all environments **and** **missing required regression test**; however the clearest single classification per the user’s request (“Clearly classify PASS, FAIL, or NOT VERIFIED…”):  
**Classification: NOT VERIFIED** (for the claimed safety property “reliably rolls back and clears identity context on exception in all deployed contexts”), with a **definite test gap (FAIL to have coverage)** documented above. The source indicates the intended behavior is correct (**PASS** in structure), but without the recommended automated test and without pooled-runtime validation the property is **not verified**.

> Recommended explicit statement: **Source path = PASS (intended). Automated exception-path regression test = ABSENT (FAIL coverage). Deployed/pooler runtime = NOT VERIFIED. Overall: NOT VERIFIED until the exact next test is added and staging pooling checks pass.**

## 9. Exact next test needed (copy/paste-ready description)

Add to `backend/authentication/tests/test_middleware.py` (inside `MiddlewareDatabaseTests`, using the same `MIDDLEWARE`/`ROOT_URLCONF` override pattern):

- Add a test view `_raise_after_identity_view` (or similar) registered in the test URLconf that raises `RuntimeError("intentional test exception")`.
- Test method steps:
  1. `resp = self.client.get(reverse("middleware-raise"), **auth_headers(HOSPITAL_ONE_ID))` → expect error status (e.g. 500) from the test client/default handling.
  2. `probe = self.client.get(reverse("middleware-db-identity"))` → expect `200`, `current_user != "authenticated"`, `claim_sub` falsy/empty, `claim_role` falsy/empty (same assertions as `test_missing_token_does_not_activate_authenticated`).
  3. (Optional) `probe2 = self.client.get(reverse("middleware-db-identity"), **auth_headers(HOSPITAL_TWO_ID))` → expect authenticated context for `HOSPITAL_TWO_ID` (proves no identity leakage from the failed first request).

This test must run against the **isolated local PostgreSQL** test database (e.g. via `TEST_DATABASE_URL` / `DomainSchemaTestRunner` setup already used), must not connect to hosted Supabase, and must not change production code except test-only URLconf/view additions in the test module.

## 10. Deployment blockers related to this audit (summary)

- No automated regression test for exception-after-identity rollback → risk of silent regressions.
- Hosted/pooler behavior not validated for transaction-local role/GUC scoping under exceptions and under connection reuse.
- Any production code path that performs DB work outside the middleware transaction or uses unusual transaction nesting could invalidate assumptions (not audited exhaustively).