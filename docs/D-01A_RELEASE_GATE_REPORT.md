# D-01A — Deployment Blocker Resolution Preparation

Date: 2026-11-23
Task type: read-only preparation and release-gate planning
Predecessor: `docs/D-01_DEPLOYMENT_READINESS_REPORT.md`

## 1. Executive summary

Release gate status: **BLOCKED**.

Two blockers from D-01 remain open:

1. **DR-01 / BUG-1:** oversized request notes are not rejected at the API boundary and can reach the database CHECK constraint, producing `500/internal_error` instead of `400/validation_error`.
2. **Release commit state:** the working tree has no staged or unstaged tracked changes, but it contains untracked audit reports and a local-only helper file. The exact tested commit cannot be proven from B-06B because that report does not record a commit identifier.

This report prepares both blockers for resolution. It does **not** implement the fix, stage files, commit, reset, stash, push, deploy, create services, modify environment files, or access production databases.

Overall release readiness after this preparation:

| Area | Status |
|---|---|
| DR-01 correction plan | `READY` |
| DR-01 code/test implementation | `BLOCKED` |
| Git branch/ref alignment | `READY` |
| Release commit decision | `BLOCKED` |
| Render/Vercel configuration planning | `NEEDS CONFIGURATION` |
| Hosted Supabase/JWKS/RLS verification | `NOT VERIFIED` |
| Linux Gunicorn runtime verification | `NOT VERIFIED` |

## 2. Part 1 — DR-01 defect preparation

### 2.1 Evidence reviewed

- `docs/B-06B_E2E_TEST_REPORT.md`, especially E10 and BUG-1.
- `docs/B-07A_DEFECT_REVIEW_REPORT.md`, especially DR-01 and remediation section 6.1.
- `backend/requests_app/serializers.py`
- `backend/requests_app/models.py`
- `backend/requests_app/views.py`
- `backend/requests_app/tests/test_api.py`
- `backend/common/errors.py`
- `supabase/migrations/0002_tables.sql`

### 2.2 Exact affected serializer and validation path

| Item | Finding |
|---|---|
| Serializer | `backend/requests_app/serializers.py::BloodRequestSerializer` |
| Field | `notes` in `Meta.fields` and `Meta.extra_kwargs` |
| Current field options | `required=False`, `allow_blank=True`, `allow_null=True`; no `max_length` |
| Model field | `backend/requests_app/models.py::BloodRequest.notes` is an unbounded `TextField` |
| Database rule | `supabase/migrations/0002_tables.sql` defines `requests_notes_length CHECK (notes IS NULL OR length(notes) <= 1000)` |
| Write views | `BloodRequestListCreateView` for POST and `BloodRequestDetailView` for PATCH use `BloodRequestSerializer` |
| Create path | `serializer.is_valid()` → `BloodRequestSerializer.create()` → `BloodRequest.objects.create(**validated_data)` |
| Update path | `serializer.is_valid()` → `BloodRequestSerializer.update()` → `super().update(instance, validated_data)` |
| Missing control | The serializer never applies the 1000-character rule, so validation passes before the database write |

Both create and update pass through the same serializer field definition. A `max_length` on that field therefore covers both POST and PATCH without view changes.

### 2.3 Why oversized notes currently return HTTP 500

The observed chain is:

1. A client submits `notes` longer than 1000 characters.
2. DRF builds the `notes` field from an unbounded `TextField`; `allow_blank` and `allow_null` affect presence/emptiness, not length.
3. `BloodRequestSerializer.is_valid()` accepts the value because no serializer-level maximum exists.
4. `create()` or `update()` writes the value to the database.
5. PostgreSQL enforces `requests_notes_length` and rejects the write.
6. No serializer, view, or application exception handler converts that database constraint failure into a field validation error.
7. `backend/common/errors.py::api_exception_handler` receives an unhandled exception, logs it, and returns the generic envelope with code `internal_error`, message about an unexpected error, `details: null`, and HTTP 500.

This matches B-06B E10: `500/internal_error`, `details_is_null=True`, no field list, and no SQL text, stack trace, or secret in the response. The database constraint remains an effective defense against invalid persistence; the defect is the wrong API status and missing field-level feedback.

### 2.4 Minimal safe correction

Recommended correction, to be implemented only in an authorized follow-up change:

```python
extra_kwargs = {
    "notes": {
        "required": False,
        "allow_blank": True,
        "allow_null": True,
        "max_length": 1000,
    },
    "status": {"required": False},
    "units": {"min_value": 1, "max_value": 10000},
}
```

Why this is the minimal safe change:

- It adds one validator to the existing serializer field.
- It preserves optional, blank, and null notes behavior.
- It applies to both POST and PATCH through the shared serializer.
- DRF will raise `rest_framework.exceptions.ValidationError`, which `api_exception_handler` already maps to `400/validation_error` with field details.
- The database CHECK constraint remains unchanged as defense in depth.
- No model change is required; `BloodRequest` is an unmanaged projection of a migration-owned table.
- No generic 500 envelope or authentication/authorization behavior changes.

Optional visibility improvement, not required for the minimal fix: define the 1000-character limit as a named constant and reference it from serializer documentation and frontend form hints so API and UI expectations remain aligned.

### 2.5 Regression tests required

Add tests to `backend/requests_app/tests/test_api.py` using the isolated local test stack only.

| ID | Scenario | Expected result |
|---|---|---|
| R1 | POST with `notes` exactly 1000 characters | `201`; stored/returned notes length is 1000 |
| R2 | POST with `notes` 1001 characters | `400/validation_error`; `error.details` contains `notes`; no request id returned; database row count unchanged |
| R3 | PATCH with `notes` exactly 1000 characters | `200`; stored notes length is 1000 |
| R4 | PATCH with `notes` 1001 characters | `400/validation_error`; `error.details` contains `notes`; stored notes value remains unchanged |
| R5 | POST/PATCH with `notes: null` and `notes: ""` | Accepted as before; null/blank storage behavior unchanged |
| R6 | Oversize POST/PATCH as hospital and as admin with explicit hospital | Both roles receive the same `400/validation_error`; no privilege-dependent behavior |
| R7 | Direct SQL insert/update beyond 1000 characters on the isolated local database | Database rejects the write; no committed invalid row |
| R8 | Error envelope inspection for R2/R4/R6 | No SQL text, stack trace, credential, secret, or database constraint name is exposed |
| R9 | Optional Unicode boundary check | Character-count behavior is consistent with the documented 1000-character contract |

Suggested test names:

- `test_create_request_with_notes_at_limit_succeeds`
- `test_create_request_with_notes_over_limit_returns_validation_error`
- `test_patch_request_with_notes_at_limit_succeeds`
- `test_patch_request_with_notes_over_limit_preserves_stored_value`
- `test_null_and_blank_notes_remain_valid`
- `test_oversize_notes_validation_is_role_independent`
- `test_database_still_rejects_oversize_notes`
- `test_oversize_notes_error_envelope_does_not_leak_details`

After implementation, rerun the full P0/P1 regression set from B-07A section 7, not only the new notes tests.

### 2.6 Compatibility risks

| Risk | Assessment | Mitigation |
|---|---|---|
| Client behavior changes from 500 to 400 | Intended and beneficial, but clients that treated 500 as a generic retry case must handle field validation | Document the contract; assert `error.code == "validation_error"` and `details.notes` |
| Frontend has no visible notes limit | `frontend/app/requests/new/page.tsx` sends trimmed notes but has no `maxLength` or boundary message | Add a UI hint/limit in a separate authorized change; keep server validation authoritative |
| Drift between API constant and SQL CHECK | Future schema changes could change 1000 without changing serializer | Use a shared documented constant and include boundary tests |
| Existing oversized rows | Database CHECK should prevent them, but hosted state was not inspected | Do not add model-wide validation that could affect unrelated update paths; verify target schema migration state before release |
| Unicode counting differences | DRF and PostgreSQL `length(text)` count characters, but product meaning should be explicit | Include one Unicode boundary test if product approves the character-based contract |
| Over-broad validation | Adding `max_length` to the model or all read paths could affect reads/admin forms | Keep the change in `BloodRequestSerializer.extra_kwargs["notes"]` only |

### 2.7 Dependency before implementation

B-07A records product decision #2 (notes and name lengths) as unapproved. Implementation should wait until an authorized owner approves **1000 characters for request notes** as the public API contract. This report prepares the change but does not grant that approval.

## 3. Part 2 — Read-only Git audit

All Git commands used were read-only. No fetch, stage, commit, reset, stash, push, checkout, or discard was performed.

### 3.1 Refs

| Item | Value |
|---|---|
| Current branch | `main` |
| Upstream | `origin/main` |
| Current commit | `351c66be5ab821285e23d1fe2aab6f3ebbd72f1b` |
| Latest local remote-tracking commit | `351c66be5ab821285e23d1fe2aab6f3ebbd72f1b` |
| Ahead / behind vs upstream | `0 / 0` |
| Head commit subject | `fix: clear stale session after failed login` |

The remote-tracking ref was read from the local repository. Because no fetch was performed, this is the latest **known** remote-tracking commit, not a network-verified remote state.

### 3.2 Working-tree status

| Area | Finding |
|---|---|
| Staged changes | None; `git diff --cached` is empty |
| Unstaged tracked changes | None; `git diff` is empty |
| Untracked files | Four files at audit time |
| Merge/rebase state | No indication of an in-progress operation in `git status` |
| Branch tracking | Clean and aligned with `origin/main` |

Untracked files at audit time:

| File | Nature | Preservation decision |
|---|---|---|
| `backend/b05b7_r.py` | Pre-existing local-only identity-alignment helper with loopback guards and local-side file references | Preserve. Do not execute, discard, or include in a release commit without explicit owner review. |
| `docs/B-06B_E2E_TEST_REPORT.md` | B-06B test evidence | Preserve. Intended release-documentation candidate. |
| `docs/B-07A_DEFECT_REVIEW_REPORT.md` | DR-01 defect-review evidence | Preserve. Intended release-documentation candidate. |
| `docs/D-01_DEPLOYMENT_READINESS_REPORT.md` | D-01 deployment-readiness audit | Preserve. Intended release-documentation candidate. |

This D-01A report was created after the Git snapshot and is also untracked at completion.

### 3.3 Is the tested implementation represented in the current branch?

| Scope | Assessment |
|---|---|
| Backend DR-01 implementation | `READY` with qualification. The serializer, model, views, error handler, and request tests reviewed for DR-01 are tracked, unmodified at HEAD, and the relevant serializer/test code dates to earlier commits. The current branch contains the implementation that was statically reviewed. |
| Exact B-06B test commit | `NOT VERIFIED`. B-06B records the date and sanitized results but not a commit SHA or timestamp, so the exact tree used for the run cannot be cryptographically proven from the report alone. |
| Frontend implementation | `NOT VERIFIED` for exact tested commit. HEAD changes `AuthProvider` and its test; B-06B F1–F4 were blocked and its frontend evidence was compiled from a temporary copy. Re-run the frontend compile/build and any approved browser checks against the exact release commit. |
| Audit evidence | `BLOCKED` from a release perspective. B-06B, B-07A, D-01, and D-01A are untracked, so they are not represented in `main` until intentionally committed or archived. |

Conclusion: the current branch is clean and contains the reviewed backend source, but release evidence is not yet committed and exact test-to-commit traceability is incomplete. Before release, an authorized owner should record the release SHA and rerun the required checks against that SHA.

### 3.4 Changes that must be preserved

All four untracked files listed in section 3.2 must be preserved. In particular:

- Do not discard `backend/b05b7_r.py`; it is a pre-existing local-only helper and may be deliberately uncommitted.
- Do not drop the B-06B/B-07A/D-01 reports; they are the audit trail for test results, the accepted defect, and deployment readiness.
- Decide explicitly which reports belong in the release commit and which should remain local evidence.
- Do not stage anything automatically as part of DR-01 implementation; the implementation change should be reviewed separately from documentation cleanup.

## 4. Part 3 — Deployment release checklist

Status values describe preparation state, not post-deployment results.

### 4.1 Blockers and code gates

| # | Gate | Status | Required action / evidence |
|---|---|---|---|
| G1 | Product approval of 1000-character notes contract | `BLOCKED` | Authorized owner approves decision #2 from B-07A. |
| G2 | DR-01 serializer fix | `BLOCKED` | Add `max_length: 1000` to `BloodRequestSerializer.extra_kwargs["notes"]` in an authorized change. |
| G3 | DR-01 regression tests | `BLOCKED` | Add R1–R9 tests; run on isolated local stack; no hosted database. |
| G4 | Full P0/P1 regression rerun | `BLOCKED` | Rerun B-07A P0/P1 matrix after the fix; record requirement-based PASS/FAIL. |
| G5 | Release commit decision | `BLOCKED` | Decide which untracked files are committed; record release SHA; do not commit as part of this read-only task. |
| G6 | Frontend workflow tests F1–F4 | `NOT VERIFIED` | Requires approved browser/E2E driver; rerun against release SHA. |

### 4.2 Backend dependencies and Linux Gunicorn

| # | Gate | Status | Required action / evidence |
|---|---|---|---|
| B1 | Python dependency manifest | `READY` | `backend/requirements.txt` is tracked and contains the pinned Django/Gunicorn/database/JWT/CORS dependencies. |
| B2 | Python runtime pin | `NEEDS CONFIGURATION` | Set Render `PYTHON_VERSION=3.14.10`; do not rely on service defaults. |
| B3 | Dependency install on Render | `NEEDS CONFIGURATION` | Build Command: `python -m pip install -r requirements.txt`, Root Directory `backend`. |
| B4 | Linux Gunicorn startup | `NOT VERIFIED` | Start Command: `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT`. Confirm import and bind on Linux during controlled build validation. |
| B5 | Django version compatibility | `NEEDS CONFIGURATION` | Confirm pinned Django 6.1.x and all dependencies install cleanly on the selected Python version. |
| B6 | Static files | `NOT VERIFIED` | API-focused repo has no confirmed `collectstatic` requirement; decide explicitly before release. |
| B7 | Migration strategy | `NEEDS CONFIGURATION` | Confirm reviewed Supabase migrations are applied by the approved process; do not silently add migrations to web startup. |
| B8 | Local-vs-Linux parity | `NOT VERIFIED` | Local evidence is Windows-based; Linux path, native packages, and process startup must be validated on Render. |

### 4.3 Vercel frontend build

| # | Gate | Status | Required action / evidence |
|---|---|---|---|
| V1 | Root directory | `READY` | Set Vercel Root Directory to `frontend`. |
| V2 | Framework preset | `READY` | Select Next.js. |
| V3 | Install command | `READY` | `npm ci` using the committed lockfile. |
| V4 | Build command | `READY` | `npm run build`. |
| V5 | Node runtime | `NEEDS CONFIGURATION` | Set Vercel Node.js Version to `24.x`; satisfies bundled Next.js minimum `>=20.9.0`. |
| V6 | Public env values at build time | `NEEDS CONFIGURATION` | `NEXT_PUBLIC_*` values are inlined at build; set before building and rebuild after any change. |
| V7 | Development login disabled | `NEEDS CONFIGURATION` | `NEXT_PUBLIC_ALLOW_DEV_LOGIN=false` or unset in Production. |
| V8 | Secret boundary | `NEEDS CONFIGURATION` | Only public API origin and public Supabase URL/key values may be used in frontend variables. |
| V9 | Build against release SHA | `NOT VERIFIED` | Trigger or validate the build only after the release commit is fixed and recorded. |
| V10 | F1–F4 browser workflows | `BLOCKED` | Execute after browser driver approval; current blocking condition is unchanged from B-06B. |

### 4.4 Render environment variables

Set all values as Render service environment variables/secrets by an authorized owner. No values are reproduced here.

| Variable | Rule |
|---|---|
| `DJANGO_SECRET_KEY` | Strong Django secret; keep secret |
| `DJANGO_DEBUG` | `false` |
| `DJANGO_ALLOWED_HOSTS` | Exact Render/custom API hostnames, comma-separated, no scheme |
| `CORS_ALLOWED_ORIGINS` | Exact HTTPS Vercel origin(s), no trailing slash, no wildcard |
| `DATABASE_URL` | Hosted PostgreSQL/Supabase connection URL; keep secret |
| `SUPABASE_URL` | Correct hosted Supabase project URL |
| `SUPABASE_JWKS_URL` | Set explicitly if required for asymmetric verification |
| `SUPABASE_JWT_SECRET` | Only for legacy HS256; leave unset when using JWKS |
| `SUPABASE_JWT_ISSUER` | Leave unset unless the project uses a non-default issuer |
| `SUPABASE_JWT_AUDIENCE` | Leave unset unless the project uses a non-default audience |
| `TEST_DATABASE_URL` | Unset in Production |
| `PYTHON_VERSION` | `3.14.10` |
| `PORT` | Supplied by Render; do not set manually |

### 4.5 Supabase production JWT/JWKS configuration

| # | Gate | Status | Required action / evidence |
|---|---|---|---|
| S1 | Correct project URL | `NOT VERIFIED` | Authorized owner confirms `SUPABASE_URL` points to the intended project. |
| S2 | Key strategy | `NEEDS CONFIGURATION` | Prefer asymmetric RS256/ES256 via JWKS; use shared-secret HS256 only if explicitly required. |
| S3 | JWKS reachability | `NOT VERIFIED` | Confirm Render service can reach the JWKS endpoint; verify cached key rotation behavior in controlled testing. |
| S4 | Issuer and audience | `NEEDS CONFIGURATION` | Default issuer path is `/auth/v1`; default audience is `authenticated`. Override only for confirmed non-default project settings. |
| S5 | Claim validation | `READY` in code; `NOT VERIFIED` live | Code requires signature, algorithm, expiry, issuer, audience, subject, and UUID subject. Verify with live test tokens in staging/controlled window. |
| S6 | Role source | `READY` in code; `NOT VERIFIED` live | Roles are resolved from `public.profiles`, not JWT role claims; verify forged-claim denial. |
| S7 | Public frontend keys | `NEEDS CONFIGURATION` | Use only public/publishable Supabase values in Vercel; never place privileged keys in browser-exposed variables. |
| S8 | Redirect configuration | `NOT VERIFIED` | Confirm authentication/password-recovery redirects use the final HTTPS frontend origin. |

### 4.6 Database connectivity and RLS

| # | Gate | Status | Required action / evidence |
|---|---|---|---|
| DB1 | Render-to-database connectivity | `NOT VERIFIED` | Confirm TLS/connectivity from the Render service to the target hosted database using approved credentials. |
| DB2 | Migration state | `NOT VERIFIED` | Confirm migrations `0001`–`0010` are applied to the target project by the approved process. |
| DB3 | Table RLS enabled | `NOT VERIFIED` | Confirm RLS on domain tables in hosted state. |
| DB4 | Anonymous access revoked | `NOT VERIFIED` | Confirm anon/PUBLIC privileges are revoked for protected tables. |
| DB5 | Authenticated grants | `NOT VERIFIED` | Confirm authenticated DML grants on domain tables and profile update limited to display name. |
| DB6 | Hospital scoping | `NOT VERIFIED` | Confirm request RLS policies restrict admin vs own-hospital access in hosted state. |
| DB7 | Claims propagation | `READY` in code; `NOT VERIFIED` live | Middleware sets verified identity/claims transaction-locally; confirm with controlled requests. |
| DB8 | Notes constraint | `READY` in migration; `NOT VERIFIED` live | Confirm `requests_notes_length` exists; run R7 direct-SQL rejection test only on isolated/approved data. |

### 4.7 CORS and allowed hosts

| # | Gate | Status | Required action / evidence |
|---|---|---|---|
| C1 | Vercel production origin fixed | `NEEDS CONFIGURATION` | Record final HTTPS origin after project/domain setup. |
| C2 | `CORS_ALLOWED_ORIGINS` | `NEEDS CONFIGURATION` | Set to exact Vercel origin(s), no wildcard. |
| C3 | `DJANGO_ALLOWED_HOSTS` | `NEEDS CONFIGURATION` | Set to exact Render/custom API hostnames, no scheme. |
| C4 | CORS preflight | `NOT VERIFIED` | Verify browser preflight and authenticated requests from the final frontend origin. |
| C5 | Host rejection | `NOT VERIFIED` | Confirm unknown hosts are rejected and no origin echo is used as an access control. |
| C6 | Redirect alignment | `NOT VERIFIED` | Confirm auth redirects, API URLs, and CORS origins all use the same final frontend host. |

### 4.8 Health checks

| # | Gate | Status | Required action / evidence |
|---|---|---|---|
| H1 | Health endpoint in code | `READY` | `/health` maps to `config.health.HealthView` and returns an OK status without authentication. |
| H2 | Render Health Check Path | `NEEDS CONFIGURATION` | Set to `/health`. |
| H3 | Health response shape | `READY` in code; `NOT VERIFIED` live | Confirm unauthenticated `200` with the documented OK body after deployment. |
| H4 | Dependency depth | `NOT VERIFIED` | Current health endpoint is liveness-style; do not treat it as database readiness. Decide whether a deeper readiness check is required. |
| H5 | Restart behavior | `NOT VERIFIED` | Confirm Render restarts unhealthy instances as expected after configuration. |

### 4.9 Post-deployment authentication tests

Run in staging or a controlled production window with approved disposable data only.

| # | Test | Expected result |
|---|---|---|
| A1 | No bearer token on protected API | `401/authentication_failed` |
| A2 | Malformed, expired, tampered, wrong-issuer, wrong-audience, unsupported-algorithm token | `401/authentication_failed`; no token or claim echoed |
| A3 | Valid admin token | Role resolves from profile; admin access works |
| A4 | Valid hospital token | Role and hospital scope resolve from profile |
| A5 | Forged JWT role claim or body role field | No privilege change; profile remains authoritative |
| A6 | Dev-login endpoint in Production | Denied because `DJANGO_DEBUG=false` |
| A7 | Hospital cross-hospital read/write | Denied; no other hospital data or created id returned |
| A8 | Password recovery redirect | Uses final HTTPS frontend origin |
| A9 | Oversized notes after DR-01 fix | `400/validation_error` with `details.notes`; no `500/internal_error` |
| A10 | Error envelope safety | No SQL text, stack trace, credential, secret, or constraint name in responses |
| A11 | Frontend guarded routes | Redirect/access-denied behavior verified after browser capability is available |

## 5. Release decision rule

Do not mark the release ready until:

1. Product decision #2 is approved.
2. DR-01 fix and R1–R9 regression tests are implemented and pass on the isolated local stack.
3. Full P0/P1 regression tests pass against the exact release SHA.
4. Untracked files are reviewed and an authorized owner creates the release commit.
5. Render and Vercel environment variables are set with exact values.
6. Hosted Supabase JWT/JWKS, migration, RLS, redirect, and connectivity checks pass in an approved environment.
7. Health, CORS, allowed-host, and authentication post-deployment checks pass.
8. F1–F4 are executed once an approved browser/E2E driver is available.

## 6. Verification and restrictions

- This report was prepared using read-only inspection only.
- No application code, tests, environment files, secrets, migrations, database rows, or RLS policies were changed.
- No Git state was changed: no staging, commit, reset, stash, push, checkout, or discard.
- No production database or hosted Supabase resource was accessed.
- No hosting service was created and no deployment was performed.
- No credentials, tokens, UUIDs, database URLs, email addresses, phone numbers, or secret values are reproduced in this report.
- The only repository change made by this task is the creation of `docs/D-01A_RELEASE_GATE_REPORT.md`.
