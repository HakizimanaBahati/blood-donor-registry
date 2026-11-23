# D-03G — Transaction and Identity Isolation Security Audit (Read-Only)

Date: 2026-11-23  
Project: Blood Donor Registry  
Scope: Read-only source and test audit of Supabase JWT verification, Django middleware identity context, PostgreSQL transaction/role/GUC handling, and existing test coverage. No hosted access, no migrations/SQL execution, no code/test/env/infrastructure changes.  
Inputs reviewed: `docs/D-03D_DATABASE_CONNECTION_SECURITY_AUDIT.md`, `docs/D-03F_DATABASE_SECURITY_REMEDIATION_PLAN.md` (planning context), plus repository files listed below.

## 1. Files inspected

**Backend configuration and middleware**
- `backend/config/settings.py` (MIDDLEWARE order, `DATABASES`, `REST_FRAMEWORK`, JWT/Supabase env wiring, logging)
- `backend/config/test_runner.py` (test DB setup context; not the middleware path)

**Authentication / JWT / authorization**
- `backend/authentication/middleware.py` (`SupabaseClaimsMiddleware`)
- `backend/authentication/jwt.py` (`verify_access_token`, `VerifiedToken`, error handling/sanitization)
- `backend/authentication/authentication.py` (`SupabaseJWTAuthentication`, DRF integration)
- `backend/authentication/permissions.py` (`IsAuthenticatedUser`, `IsAdminUser`, `IsHospitalUser`)
- `backend/authentication/services.py` (referenced behavior: app user resolved from `profiles` by verified `sub`; not re-pasted in full here but used in reasoning)

**Tests (relevant)**
- `backend/authentication/tests/test_middleware.py` (mocked statement tests + real DB tests via `__middleware-db-identity__` view)
- `backend/authentication/tests/test_rls.py` (manual `SET LOCAL ROLE authenticated` + claim GUC setup in transactions; asserts RLS-related DB errors/behavior)
- `backend/common/test_helpers.py` (`auth_headers`, `make_token`, `ADMIN_ID`, `HOSPITAL_ONE_ID`, `HOSPITAL_TWO_ID`, etc.)
- `backend/requests_app/tests/test_api.py` (API-level isolation examples: hospital sees only own requests, cannot view/modify another hospital’s request via API; admin create for explicit hospital; notes validation unrelated to identity but present)

**Migrations (context only, not executed)**
- `supabase/migrations/0004_functions.sql`, `0005_rls.sql`, `0009_harden_function_search_paths.sql`, `0010_revoke_rls_auto_enable.sql` (referenced for `bdr_*`, RLS intent)

**Docs referenced**
- `docs/D-03D_DATABASE_CONNECTION_SECURITY_AUDIT.md`
- `docs/D-03F_DATABASE_SECURITY_REMEDIATION_PLAN.md`

## 2. Middleware execution sequence (source evidence)

**MIDDLEWARE order (`backend/config/settings.py`):**
1. `corsheaders.middleware.CorsMiddleware`
2. `django.middleware.security.SecurityMiddleware`
3. `authentication.middleware.SupabaseClaimsMiddleware`

**`SupabaseClaimsMiddleware.__call__` (`backend/authentication/middleware.py`):**
1. Generates `request.auth_debug_request_id` (short hex) and logs `Auth.middleware invoked` (path/method/headers/scheme/logger metadata). No token/secret values are logged by this middleware in the shown code.
2. Reads `request.META.get("HTTP_AUTHORIZATION", "")`, computes `header_present`, `scheme` for logging.
3. If header starts with `Bearer ` (case-insensitive check via `header.lower().startswith("bearer ")`): extracts `token = header.split(None,1)[1].strip()`, calls `verify_access_token(token)`.
   - On `SupabaseTokenError`: sets `verified = None`, sets `request.supabase_auth_error = exc` (DRF authentication layer later maps to authentication failure/401 behavior per `SupabaseJWTAuthentication`).
   - On success: sets `request.verified_token = verified`, clears `request.supabase_auth_error = None`.
4. Opens `with transaction.atomic(): ...` **unconditionally** for every request (no global `ATOMIC_REQUESTS=True` in settings; atomicity is middleware-driven).
5. If `verified` is truthy (inside the same transaction): obtains a DB cursor and executes:
   - `SELECT set_config('request.jwt.claim.sub', %s, true)` with `verified.subject`
   - `SELECT set_config('request.jwt.claim.role', %s, true)` with literal `"authenticated"`
   - `SET LOCAL ROLE authenticated`
6. Calls `self.get_response(request)`, stores `response`, ends the `transaction.atomic` block (commit/rollback follows Django’s transaction rules for that block), returns `response`.

**DRF authentication (`backend/authentication/authentication.py`, `SupabaseJWTAuthentication`):**
- Runs in the request lifecycle after middleware (typical DRF flow). If `Authorization` header missing: returns `None` (no credentials). If malformed scheme/parts: raises `AuthenticationFailed`. If token undecodable as ASCII: raises `AuthenticationFailed`.
- Reuses `request.verified_token` if set by middleware; if middleware set `request.supabase_auth_error` and no verified token, it raises `AuthenticationFailed(str(auth_error))`.
- If neither present (e.g. different path), it calls `verify_access_token(token)` again (duplicate verification possible in that branch) and on `SupabaseTokenError` raises `AuthenticationFailed(str(exc))`.
- On success, resolves app user via `get_app_user(verified.subject)`. If no valid registry profile/role: raises `PermissionDenied(...)`. Otherwise returns `(user, verified)`.

**JWT verification (`backend/authentication/jwt.py`):**
- Validates header parse, requires `alg` in `settings.JWT_ALGORITHMS`, rejects `alg == "none"`. Requires claims `exp`, `sub`, `iat` via PyJWT `options["require"]`. Verifies signature, exp, aud, iss (issuer added to decode kwargs only if configured). 
- `HS256`: requires `SUPABASE_JWT_SECRET`; decodes with it.
- Asymmetric (`RS256`/`ES256` per allowed set): fetches signing key via cached `PyJWKClient` from `SUPABASE_JWKS_URL` (`_jwk_client()`), decodes with that key. JWKS retrieval/network issues are caught and converted to a generic `SupabaseTokenError("Access token verification is temporarily unavailable", category="jwks_retrieval")` style path (message sanitized in logs).
- On success constructs `VerifiedToken(subject=str(claims["sub"]), claims=claims)` after validating `subject` parses as a UUID (else raises `SupabaseTokenError` with category `subject`).
- All failures are logged via sanitized diagnostics; messages returned to callers are the `SupabaseTokenError` strings (safe in intent per code comments).

**Permissions (`backend/authentication/permissions.py`):**
- `IsAuthenticatedUser`: requires `request.user` truthy and `is_authenticated`. `IsAdminUser`: also requires `user.is_admin`. `IsHospitalUser`: requires authenticated, `is_hospital`, and non-null `hospital_id`. These are **application-layer** checks (not DB RLS). 

## 3. Transaction and identity-context lifecycle (source evidence)

**Lifecycle for a request that includes a valid Bearer token (verified by middleware):**
1. Middleware verifies token **before** opening the transaction? No: verification happens in step 3 (outside the `transaction.atomic()` block). Then the transaction is opened in step 4 and, if verified, DB session context is set in step 5 **inside** that same transaction. So **JWT verification occurs before any DB identity/role setup SQL runs and before the request handler executes inside that transaction scope** (middleware sets context, then calls `get_response`).
2. Inside `transaction.atomic()`, if verified: the three statements run on the default Django DB connection cursor: two `SELECT set_config(..., true)` calls (transaction-local GUCs) and `SET LOCAL ROLE authenticated` (transaction-local role change in effect for the transaction). This happens **before** `self.get_response(request)` is invoked, so view/ORM work executed during the request runs within that same transaction context (unless views open nested transactions in ways that change semantics—see gaps).
3. After the view returns, control returns to middleware; the `atomic` block ends. Transaction commit/rollback is handled by Django’s transaction management for that block (normal behavior). With `conn_max_age=0` in settings (`DATABASES["default"]` parsed with `conn_max_age=0`), Django does not keep persistent connections by that setting; combined with transaction-local settings, this is intended to avoid cross-request leakage on reused Django connections—**but external poolers are not controlled by repo** (see gaps).

**Lifecycle for a request with no Bearer token (or token present but verification failed in middleware):**
- Middleware does **not** call `verify_access_token` in a way that sets `verified` when header absent; when header present but verification fails it sets `request.supabase_auth_error` and leaves `verified False`. It still enters `transaction.atomic()` and does **not** execute the claim/role SQL. Thus the DB session runs as the **login role of `DATABASE_URL`** for that transaction (with no app-set `request.jwt.claim.*` GUCs and no `SET LOCAL ROLE authenticated` from middleware). DRF then typically rejects unauthenticated/protected endpoints (401/403) before business logic that assumes an app user.

**Lifecycle for exceptions/early returns inside the atomic block (source-level reasoning):**
- Middleware wraps the whole request in `transaction.atomic()`. If `get_response(request)` raises, Django’s `atomic` will mark/rollback the transaction on exception by default (standard behavior) unless handled; the middleware does not catch exceptions around `get_response` in the shown code, so exceptions propagate after the block context exits in the usual way. The transaction-local GUCs and `SET LOCAL ROLE` are scoped to that transaction and are discarded with the transaction end/rollback context in PostgreSQL terms—consistent with `set_config(..., true)` and `SET LOCAL ROLE` behavior. **This is source-structure evidence; exact runtime rollback semantics for all error types should be validated in integration tests (not proven here).**

**`transaction.set_rollback(True)` in tests:** `MiddlewareDatabaseTests.test_role_and_claims_revert_when_transaction_ends` demonstrates that after the middleware transaction is rolled back (test forces rollback inside an outer atomic in that test pattern?), the identity view outside that scoped transaction shows non-authenticated user and empty/falsey claim values. This is **test evidence** (real DB, local isolated test cluster per test docstring) that the context is not retained beyond the intended transaction boundary in that test scenario.

## 4. Confirmed security properties (source + test evidence)

The following are **confirmed by source code and/or existing tests** (local/isolated test DB as described in tests):

1. **JWT verification happens before DB identity context is applied by middleware.** Evidence: `verify_access_token` is called in `SupabaseClaimsMiddleware` before entering `transaction.atomic()` and before executing any `set_config`/`SET LOCAL ROLE` SQL. (`middleware.py`, `jwt.py`.)
2. **For verified tokens, claim GUCs are set transaction-locally and role is switched to `authenticated` inside the same request-wrapping transaction as view handling.** Evidence: middleware sets GUCs and `SET LOCAL ROLE authenticated` inside `with transaction.atomic():` and only after verification; then calls `get_response`. (`middleware.py`.) Mocked test asserts exact SQL sequence and that claims use `set_config(..., true)` and role uses `SET LOCAL ROLE authenticated` (not `SET ROLE`). (`test_middleware.py::MiddlewareStatementsTests`.)
3. **Missing/invalid tokens do not activate the authenticated DB role in middleware.** Evidence: mocked tests show no `cursor.execute` calls and no `verified_token` attribute set on request when header missing or when verification raises `SupabaseTokenError`. (`test_middleware.py`.)
4. **Real DB test (local isolated cluster):** with a valid token and middleware active, the test view observes `current_user == "authenticated"`, `claim_sub == SUBJECT`, `claim_role == "authenticated"`. With missing token, observes non-authenticated `current_user` and falsy claim values. (`test_middleware.py::MiddlewareDatabaseTests`.)
5. **Transaction/rollback behavior (test evidence):** after forcing rollback in the test pattern described, a subsequent request/view observation shows context reverted (non-authenticated, empty claims) — indicates transaction-scoped effect in that scenario. (`test_middleware.py::test_role_and_claims_revert_when_transaction_ends`.)
6. **RLS helper/policy intent is exercised in DB-level tests (manual context setup):** `test_rls.py` shows that when `authenticated` role is set with an empty `request.jwt.claim.sub`, reading `public.donors` returns count `0` in that test setup (demonstrating RLS/filtering effect under that context in the test DB). Also tests that a hospital profile cannot promote its own role via SQL under the simulated authenticated+claim context (expects `DatabaseError`). These are **simulated middleware context** tests, not end-to-end through HTTP middleware in the same test class except via patterns shown.
7. **API-level application isolation (partial):** `requests_app/tests/test_api.py` verifies hospital sees only own requests, cannot view/modify another hospital’s request (404), admin can create for another hospital when specified, and role-dependent behaviors. This is **application-layer** enforcement plus ORM/RLS behavior in the test environment (per comments in that file about RLS active vs legacy in some paths) — it is evidence of API behavior, not a direct proof of DB RLS being enforced against a bypassing role in production.

## 5. Gaps and unresolved questions (cannot be fully proven from source/tests alone)

1. **Whether `SET LOCAL ROLE authenticated` and claim GUCs are applied in the exact same transaction scope as all protected ORM queries in every code path.** Source shows middleware opens one `transaction.atomic()` around `get_response`. Most views run inside that call; however, if any view explicitly opens a new transaction boundary in conflicting ways, uses `transaction.atomic()` nested differently, or if background tasks/celery/management commands bypass this middleware, context may differ. **Not exhaustively audited across all apps/views beyond inspected files.**
2. **Exception paths inside `get_response`:** middleware does not catch exceptions; Django’s `atomic` will roll back on exception by default in most cases, but behavior depends on savepoints/nesting and custom transaction handling. No explicit test observed for “middleware set role/GUCs then view raises → transaction rolls back and context not leaked.” **Runtime/transaction behavior under failures not fully proven by tests.**
3. **Early returns / short-circuiting in views before DB access:** not harmful to security if no DB access occurs under wrong context; but if any code path performs DB writes/reads before authentication is enforced in an unexpected way, risk exists. Current design sets context in middleware early and enforces auth in DRF permissions—**ordering is generally correct in Django request flow**, but edge cases (e.g. custom middleware, signals) not audited.
4. **Middleware ordering bypass risk (conceptual):** `CorsMiddleware` runs before `SecurityMiddleware` before `SupabaseClaimsMiddleware`. That means CORS/Security run before identity/DB context is set by this middleware. No evidence in inspected code that CORS/Security perform protected DB queries using the app’s RLS context; they typically operate on request/response. **No direct code evidence of bypass, but a full audit of all middleware in the project stack (including third-party additions not shown) is out of scope.**
5. **`SupabaseJWTAuthentication.authenticate` may re-verify tokens** if `request.verified_token` not set (e.g. if middleware did not run or set it). This duplicates work but is a **separate verification step** (not the same as DB context). DB context is only set by middleware when it verifies successfully. If a future code path sets `verified_token` inconsistently, risk of mismatch exists—**not observed, but possible by refactor.**
6. **Unauthenticated requests can access protected tables through the configured database role?** **Not proven by source alone for hosted DB.** Source shows middleware does not set authenticated role/GUCs for unauthenticated requests (so DB runs as login role). Whether the login role has excessive privileges (superuser/BYPASSRLS or broad grants) is a **deployment/hosted fact (NOT VERIFIED)** per D-03D/D-03F. Repo does not prevent a misconfigured login role.
7. **Supabase session pooling compatibility:** no pooler config in repo. Transaction-local `SET LOCAL ROLE` and `set_config(..., true)` inside `transaction.atomic()` are the intended pattern, but behavior under Supabase pooler modes (transaction/session) is **not verified** by tests or code. Risk of context leakage or role/GUC not applied as expected is **unresolved at runtime** until tested.
8. **No tests observed for:** alternating identities in rapid succession against the same deployed/pooler-backed service to prove no leakage (only mocked unit logic and a simple rollback test); concurrent requests proving isolation under concurrency; end-to-end “Hospital A token then Hospital B token” isolation verified through the full middleware+DRF+DB path in a single test suite run against a pooler-like setup; tests that explicitly assert `SET LOCAL ROLE` is used (mocked test does assert, which is good) across all relevant paths.
9. **`test_rls.py` uses manual SQL context** (sets role/GUCs directly) to probe RLS behavior in the test DB. This is useful but **does not test the middleware code path** end-to-end for those scenarios except indirectly; it tests “if context is set this way, RLS behaves…” which complements but does not replace middleware integration coverage.
10. **Hosted migration/RLS/grant state:** tests run against the local test schema built by `DomainSchemaTestRunner`/migrations in repo context (per test runner). Hosted Supabase may differ (**NOT VERIFIED**).

## 6. Existing test coverage (what exists)

### 6.1 Middleware (`backend/authentication/tests/test_middleware.py`)
- **Mocked (`MiddlewareStatementsTests`, `SimpleTestCase`, no DB):**
  - Valid Bearer token → calls `verify_access_token` once, returns 200 from dummy view, executes exactly: `set_config('request.jwt.claim.sub', [SUBJECT], true)`, `set_config('request.jwt.claim.role', ['authenticated'], true)`, `SET LOCAL ROLE authenticated`.
  - Asserts role switch is `SET LOCAL ROLE authenticated` (not `SET ROLE ...`) and that the first two statements are called with the transaction-local flag semantics implied by the SQL string ending `, true)`.
  - Invalid token (`SupabaseTokenError`) → `verify_access_token` called, no DB cursor executes, middleware still returns response from view after transaction? (test sets view to return `HttpResponse("ok")` and middleware calls it; in that mocked flow the cursor is patched so no real SQL—test asserts `cursor.execute.assert_not_called()`).
  - Missing Authorization header → no verification, no DB executes, no `verified_token` attribute set.
- **Real DB (`MiddlewareDatabaseTests`, `TestCase`, local isolated test cluster):**
  - Overrides `MIDDLEWARE` to only `authentication.middleware.SupabaseClaimsMiddleware`, sets `ROOT_URLCONF` to test URLconf with view `__middleware-db-identity__/` that queries `current_user`, `current_setting('request.jwt.claim.sub', true)`, `current_setting('request.jwt.claim.role', true)` and returns JSON.
  - Valid token via `auth_headers(HOSPITAL_ONE_ID)`: expects `current_user == "authenticated"`, `claim_sub == SUBJECT`, `claim_role == "authenticated"`.
  - Missing token: expects `current_user != "authenticated"` and falsy `claim_sub`.
  - Transaction rollback test: inside `transaction.atomic()` sets rollback, observes inside that middleware-set context is present for that request in that flow? then outside observes reverted context (non-authenticated, falsy claim). This demonstrates transaction scoping in that test construct.

### 6.2 RLS (`backend/authentication/tests/test_rls.py`)
- **Real DB tests (local):**
  - `test_hospital_cannot_promote_its_own_profile_via_sql`: sets `SET LOCAL ROLE authenticated`, sets `request.jwt.claim.sub` to `HOSPITAL_ONE_ID` in a transaction, attempts to `UPDATE public.profiles SET role='admin' WHERE id = HOSPITAL_ONE_ID` inside a nested transaction and expects `DatabaseError`; finally resets role and clears claim GUC in a finally block. (Simulates middleware context manually.)
  - `test_anonymous_sql_user_cannot_read_donors`: sets `authenticated` role and empty `request.jwt.claim.sub`, selects count from `public.donors`, expects `0`. Resets in finally block.

### 6.3 API tests (`backend/requests_app/tests/test_api.py`, representative)
- Unauthenticated → 401.
- Hospital create for own hospital succeeds; cannot create for another hospital (400/403 depending on RLS/context path noted in comments) and no created id returned.
- Admin can create for explicit hospital.
- Hospital sees only own requests (`hospital_id` filtered in results).
- Hospital cannot view or modify another hospital’s request → 404.
- Various validation/notes tests (not identity-isolation focused). **No test shown that alternates between two different hospital JWT identities in the same test to assert no cross-contamination beyond the “sees only own requests” list test style;** list test uses `HOSPITAL_ONE_ID` token and asserts all results are `HOSPITAL_ONE`. There is also `HOSPITAL_TWO` used in setup/create cases (admin creates for `HOSPITAL_TWO`, hospital tries to access another’s request) — these demonstrate scoping behavior in those scenarios but do not form an explicit “two-hospital concurrent/alternating session isolation matrix” test.
- Admin tests cover admin listing all requests and admin creating for another hospital (presence in cases like `test_admin_can_create_for_explicit_hospital`, and parameterized-like logic in `test_r6_oversize_notes_validation_is_role_independent` includes admin+`HOSPITAL_TWO`). No dedicated “admin sees only intended data per policy in cross-tenant edge cases” beyond existing coverage is evident from the excerpt.

### 6.4 What is **not** covered (gaps)
- No automated test proving **no identity leakage under alternating authenticated identities** in the same process/transaction context in a way that simulates pooling (e.g. back-to-back requests with different `sub`s using the same DB connection session in a test harness) beyond the single-transaction rollback test.
- No automated test for **concurrent requests** exercising middleware + RLS isolation.
- No automated test that, for a verified token, asserts the middleware set context is visible to ORM queries executed in the view **and** that a subsequent request without token does not inherit it (beyond the `MiddlewareDatabaseTests` cases shown).
- No test asserting behavior when `get_response` raises after setting DB context (rollback/cleanup) in an HTTP middleware test.
- No end-to-end test that a hospital user A cannot read hospital user B’s requests **and** also cannot escalate via profile updates in the same integrated flow beyond `test_rls.py` manual SQL case (which is a good unit of RLS behavior but not the full HTTP stack except indirectly).
- No tests for Supabase pooler modes (not applicable to local Django test DB setup in the usual way).

## 7. Required additional tests (recommended, not implemented here)

### 7.1 Transaction/exception safety (unit/integration, local DB)
- Test: request with valid Bearer token causes middleware to set context, but view raises an exception → transaction rolls back and a subsequent request (or a direct DB identity probe) shows no authenticated/claim context leaked from that failed request. Assert via the same `__middleware-db-identity__` style view or a dedicated probe.

### 7.2 Alternating identities (no pooling simulation but strong regression)
- Test (Django `TestCase`/`APITestCase` or custom client): perform sequential requests: (a) hospital A token → assert scoped results to A; (b) hospital B token → assert scoped results to B (no A data); (c) hospital A token again → assert scoped results to A. Use real middleware + real DRF auth against local test DB (as in existing middleware DB tests pattern) to catch regressions in context clearing.

### 7.3 Two-hospital isolation matrix (API + optional DB assert)
- Explicit tests: Hospital A lists requests → only A’s `hospital_id`; attempt to GET/PATCH/DELETE Hospital B’s request ID → 404. Repeat for Hospital B vs A. Complements existing `requests_app` tests (some exist) by being named/structured as an isolation matrix and, if desired, by also asserting no leakage in a second call.

### 7.4 Admin vs tenant isolation
- Tests: admin can list all requests (or per policy) and cannot be wrongly scoped to a single hospital by middleware/app logic; hospital cannot perform admin-only actions (already partially covered by permissions) and cannot see other hospitals’ data via list/detail as designed.

### 7.5 Concurrency (careful, environment-dependent)
- If feasible in CI/test environment, a small concurrent test (threads/async clients carefully coordinated) that sends interleaved authenticated requests for different users and checks response scoping. **Note:** Django’s test client and DB transaction behavior can be limiting; may require a separate integration harness. Mark as **best-effort** and document limitations.

### 7.6 Pooler/supabase-like staging tests (manual + scripted, not unit tests in repo)
- Against a controlled staging Supabase/Postgres with the chosen pooler mode and the corrected `DATABASE_URL` role: run alternating-identity and basic load tests as in D-03F Q7/Q8, record sanitized results. These are **required before production/demo trust** in RLS, not replaceable by local unit tests alone.

## 8. Exact implementation recommendations (if needed)

**No code changes are required solely to “pass” the source audit** for the behaviors already implemented, but the following are **recommended improvements** (to be done only with explicit approval if they change behavior/code):

1. **Add a middleware/transaction safety test for exceptions:** e.g. a temporary test view that raises after middleware set context is not directly observable, but you can test by having the view raise and then hitting the identity probe view in a new request (as in existing tests) to confirm no leakage—already partially covered by rollback test style; consider an explicit test that simulates a view exception and asserts post-exception request has no leaked context.
2. **Harden `SupabaseJWTAuthentication` to avoid redundant verification edge cases:** currently it may verify again if `verified_token` missing. Document/invariant: middleware is responsible for setting DB context for verified requests; authentication can be defensive, but ensure no path sets DB context outside middleware. (Low priority if middleware always runs.)
3. **Add explicit API integration tests for two-hospital alternating identities** in `requests_app` (or a dedicated isolation test module) to prevent regressions: e.g. `test_hospital_isolation_alternating_requests` that toggles between `HOSPITAL_ONE_ID` and `HOSPITAL_TWO_ID` tokens.
4. **Do not relax RLS or role model** to fix pooling issues; if pooler incompatibility is found, prefer approved connection/pooler strategy changes per D-03F.
5. **Documentation:** add a short note in `backend/authentication/middleware.py` (or repo docs) stating the invariant “JWT verified before DB context set; context is transaction-local and set only for verified Bearer tokens inside middleware transaction”—this mirrors current behavior and aids reviewers. (Doc-only change; still requires approval if modifying repo files.)

## 9. Deployment blockers (from this audit + D-03D/D-03F context)

- **Hosted DB role not verified safe:** login role must be non-superuser, no `BYPASSRLS`, able to `SET ROLE authenticated`, least privilege (D-03D/D-03F). **Not verifiable from repo/tests.**
- **Hosted migration/RLS/grants state not verified** against repo 0001–0010 (including policies/grants/helpers). **Not verifiable here.**
- **Supabase pooler mode/topology not verified** for compatibility with transaction-local `SET LOCAL ROLE` and transaction-local claim GUCs; risk of context leakage or incorrect enforcement under pooling. **Not verified by tests.**
- **No automated proof of alternating-identity / concurrency isolation** under production-like pooling; required staging validation remains open (D-03F Q7/Q8).
- **Unauthenticated DB access risk** depends entirely on login role privileges (middleware sets no authenticated context for unauthenticated requests). **Not verified on hosted DB.**

## 10. Final assessment

**Assessment: PASS WITH CONDITIONS**

**Rationale (source/test evidence):**
- Source code **clearly** performs JWT verification in `SupabaseClaimsMiddleware` **before** setting any DB identity/role context (`set_config` for `request.jwt.claim.sub`/`role` with `true`, then `SET LOCAL ROLE authenticated`) and does so **inside `transaction.atomic()`** before calling the view. Mocked tests assert the exact SQL sequence and transaction-local intent; real DB middleware tests confirm the observed `current_user` and claim GUCs for valid vs missing tokens and show rollback behavior in the tested scenario. RLS helper intent and some RLS behaviors are covered by `test_rls.py` with manual context setup, and API tests demonstrate application-layer scoping in common cases.
- However, **runtime safety for hosted deployment is not proven** by these tests: hosted role attributes, hosted migration/RLS/grants, pooler compatibility, exception-path behavior in all cases, alternating/concurrent identity leakage under pooling, and unauthenticated DB privilege posture are **not verified**. Per D-03D/D-03F, deployment must satisfy those corrections and validation steps before being treated as safe for tenant isolation.

**If forced to choose only from PASS / PASS WITH CONDITIONS / NOT READY:** **PASS WITH CONDITIONS** (code/test evidence supports the intended design; conditions are the hosted/pooling/validation items above). 

**NOT READY** would be the label only if the question were “ready for production/demo deployment today without further checks”—in that strict operational sense the answer is **NOT READY** until the listed conditions are satisfied; this audit’s formal assessment label for the **code+test posture reviewed here** is **PASS WITH CONDITIONS** with the explicit note that operational readiness is gated by those conditions.