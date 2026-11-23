# D-02D — Production Configuration and Render Readiness Review

Date: 2026-11-23  
Task type: read-only review (no source/config/infra changes, no deployments, no hosted access)  
Branch: `main` (tracked worktree modified by D-02C: `backend/config/settings.py`, `backend/config/tests/test_settings.py`; preserved untracked files present)

## 1. Review of current changes (D-02C) against reports

| Item | Evidence (current repo) | Assessment |
|---|---|---|
| Middleware order | `backend/config/settings.py`: `MIDDLEWARE = [corsheaders.middleware.CorsMiddleware, django.middleware.security.SecurityMiddleware, django.middleware.common.CommonMiddleware, authentication.middleware.SupabaseClaimsMiddleware]` | Correct: `SecurityMiddleware` immediately after `CorsMiddleware`. Consistent with D-02B/D-02C. |
| CSRF trusted origins | Parsed from `CSRF_TRUSTED_ORIGINS` only (comma split/strip), empty if unset; not derived from CORS; no hardcoded deployment domains. | Correct and matches D-02C plan (explicit env only). |
| Secure cookies | `SESSION_COOKIE_SECURE = not DEBUG`, `CSRF_COOKIE_SECURE = not DEBUG` (production -> True when `DJANGO_DEBUG=false`). | Correct and matches D-02C. |
| HTTPS redirect / proxy | `SECURE_SSL_REDIRECT = False`; `SECURE_PROXY_SSL_HEADER` not set. Comment states HTTPS at Render initially and do not trust forwarded proto until verified. | Correct and matches D-02C/D-02B. |
| HSTS | `SECURE_HSTS_SECONDS = 0`, `SECURE_HSTS_INCLUDE_SUBDOMAINS = False`, `SECURE_HSTS_PRELOAD = False`; explicit security headers set (`SECURE_CONTENT_TYPE_NOSNIFF`, `SECURE_REFERRER_POLICY="same-origin"`, `SECURE_CROSS_ORIGIN_OPENER_POLICY="same-origin"`, `X_FRAME_OPTIONS="DENY"`). | Correct initial rollout posture. |
| CORS | `CORS_ALLOWED_ORIGINS` from `CORS_ALLOWED_ORIGINS` env (default `http://localhost:3000`), `CORS_ALLOW_CREDENTIALS = False`, no wildcard in code. | Correct; no change to credentials behavior. |
| Host handling | `ALLOWED_HOSTS` parsed from `DJANGO_ALLOWED_HOSTS` (default local set). No automatic Render hostname appended in code. | Explicit-only behavior preserved (consistent with reports). |
| Auth / RLS / DB behavior | `REST_FRAMEWORK` unchanged (Supabase JWT auth, `IsAuthenticatedUser`, `UNAUTHENTICATED_USER=None`, JWT algs `HS256,RS256,ES256`). No DB/RLS model/migration changes in D-02C files. | No weakening observed; matches D-02C “no changes to authentication, RLS, or production DB configuration”. |
| Health endpoint | `backend/config/urls.py` maps `path("health", HealthView.as_view(), name="health")` -> `/health`; `backend/config/health.py` unauthenticated, no DB access, returns `{"status": "ok"}`. | Correct for Render liveness probe path. |
| WSGI entry | `backend/config/wsgi.py` sets `DJANGO_SETTINGS_MODULE=config.settings`, exposes `application` via `get_wsgi_application()`. | Matches proposed start command target `config.wsgi:application`. |
| Requirements | `backend/requirements.txt` pinned set includes Django, DRF, psycopg[binary], dj-database-url, PyJWT[crypto], django-cors-headers, python-dotenv, gunicorn, coverage. | Matches D-02A/D-01A expectations (Gunicorn pinned). |
| Tests (D-02C) | `backend/config/tests/test_settings.py` covers DB fallback, middleware order, secure cookies, local defaults, CORS creds, CSRF trusted origins, HSTS off, host validation, auth config unchanged, health behavior. | Consistent with D-02C report (17 settings tests). Full backend suite reported 120 passed in D-02C validation context. |

## 2. Environment variable register (placeholders only; no real secrets)

Notes:
- “Where configured” reflects intended deployment split: **Render** for the Django API service; **Vercel** for the Next.js frontend. Any Supabase dashboard values are not “configured in code” but are inputs to the variables below.
- Never store production secrets in git or `.env` committed files; use platform secret stores.

| Variable | Required / Optional | Purpose | Example format (placeholder only) | Where configured | Sensitive? |
|---|---|---|---|---|---|
| `DJANGO_DEBUG` | Required (production) | Enables/disables debug mode; gates prod guards and cookie defaults. Must be `false` on Render. | `false` | Render (env var) | No |
| `DJANGO_SECRET_KEY` | Required (production) | Django cryptographic signing key. Startup fails if missing when `DJANGO_DEBUG=false`. | `<random-long-secret>` | Render (secret env var) | **Yes** |
| `DJANGO_ALLOWED_HOSTS` | Required (production) | Comma-separated exact hostnames allowed (no scheme). Must include Render service/custom API host(s) used by probes and clients. | `api.example.com,api-xxxxx.onrender.com` | Render (env var) | No (hostnames only) |
| `DATABASE_URL` | Required (production) | Postgres connection URL for the API (hosted DB). Must point to intended production database; use least-privilege RLS-bound role. | `postgresql://<db_user>:<db_password>@<db_host>:5432/<db_name>` | Render (secret env var) | **Yes** (contains credentials) |
| `CORS_ALLOWED_ORIGINS` | Required (production) | Comma-separated exact HTTPS frontend origin(s). No wildcard, no trailing slash. | `https://<frontend-app>.vercel.app` | Render (env var) | No |
| `CSRF_TRUSTED_ORIGINS` | Optional (only if Django CSRF used) | Comma-separated explicit HTTPS origins for Django CSRF when applicable. Do **not** derive from CORS; set only when needed. | `https://<frontend-app>.vercel.app` | Render (env var) | No |
| `SUPABASE_URL` | Required (unless fully overriding issuer/JWKS) | Supabase project URL; used to derive JWKS/issuer defaults if not overridden. | `https://<project-ref>.supabase.co` | Render (env var) | No (project URL) |
| `SUPABASE_JWT_SECRET` | Optional (legacy HS256 only) | Legacy shared secret for HS256 token verification. **Do not** use service-role/secret API keys. Leave unset when using asymmetric JWKS. | `<hs256-secret-if-used>` | Render (secret env var) | **Yes** |
| `SUPABASE_JWKS_URL` | Optional (recommended explicit in some setups) | JWKS endpoint URL for asymmetric verification. If empty and `SUPABASE_URL` set, derived as `<SUPABASE_URL>/auth/v1/.well-known/jwks.json`. | `https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json` | Render (env var) | No (URL) |
| `SUPABASE_JWT_ISSUER` | Optional (override if non-default) | Expected JWT issuer. If empty and `SUPABASE_URL` set, derived as `<SUPABASE_URL>/auth/v1`. | `https://<project-ref>.supabase.co/auth/v1` | Render (env var) | No |
| `SUPABASE_JWT_AUDIENCE` | Optional (override if non-default) | Expected JWT audience (default in code is `authenticated`). | `authenticated` | Render (env var) | No |
| `TEST_DATABASE_URL` | **Must NOT be set on Render** (local/test only) | Used only in local/debug fallback paths per code; production requires `DJANGO_DEBUG=false` and explicit `DATABASE_URL`, so fallback is blocked. | `postgresql://<local_test_user>:<local_test_password>@127.0.0.1:5432/<local_test_db>` | Local/test environments only (not Render) | **Yes** (if set locally) |
| `PYTHON_VERSION` | Required (Render) | Pins Python runtime on Render (recommended `3.14.10`). No repo pin file found. | `3.14.10` | Render (env var) | No |
| `PORT` | Provided by platform | Render supplies `$PORT`; do not set manually. | (platform-provided) | Render (automatic) | No |
| `RENDER_EXTERNAL_HOSTNAME` | Provided by platform | Render may set this automatically; code does not currently append it to `ALLOWED_HOSTS`. You must still set `DJANGO_ALLOWED_HOSTS` explicitly to include probe/custom hostnames. | (platform-provided) | Render (automatic) | No |

**Frontend (Vercel) variables (for completeness; not backend env):**
| Variable | Required / Optional | Purpose | Example format (placeholder only) | Where configured | Sensitive? |
|---|---|---|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | Required (frontend build/runtime as configured) | Base URL for API calls from browser to Django API. | `https://<api-host>.onrender.com` | Vercel (env var) | No |
| `NEXT_PUBLIC_SUPABASE_URL` / publishable key vars | As per frontend setup | Supabase public client config (never service/secret keys). | `https://<project-ref>.supabase.co`, `<public-publishable-key>` | Vercel (env var) | Public keys only (not server secrets) |

**Remaining ambiguity to resolve before production cutover (no secrets):**
- Exact production API hostname(s) for Render (and any custom domain) to place in `DJANGO_ALLOWED_HOSTS` and Render Health Check behavior expectations.
- Exact canonical Vercel HTTPS origin(s) for `CORS_ALLOWED_ORIGINS` (apex vs `www`, preview vs production policy).
- Whether `CSRF_TRUSTED_ORIGINS` will be needed at launch (current API is token-authenticated; set only if a cookie/CSRF flow is introduced).
- Whether Render forwards `X-Forwarded-Proto` reliably enough to justify enabling `SECURE_PROXY_SSL_HEADER` later (currently unset by design).

## 3. Render configuration (verified from repo/docs)

| Setting | Required value / guidance | Status |
|---|---|---|
| Root Directory | `backend` | **READY** (repo layout matches) |
| Build Command | `pip install -r requirements.txt` (or `python -m pip install -r requirements.txt`) | **NEEDS CONFIGURATION** (must be set in Render UI/IaC) |
| Start Command | `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT` | **NEEDS CONFIGURATION** (must be set) |
| Health Check Path | `/health` (expects HTTP 200 from `HealthView`) | **NEEDS CONFIGURATION** (must be set in Render) |
| Python runtime | `PYTHON_VERSION=3.14.10` (no repo runtime file) | **NEEDS CONFIGURATION** (set explicitly on Render) |
| `DJANGO_ALLOWED_HOSTS` | Exact Render service hostname(s) and any custom API domain(s), comma-separated, no scheme (e.g. `api.example.com,<service>.onrender.com`). Must include the host used by Render health probes. | **NEEDS CONFIGURATION** |
| `CORS_ALLOWED_ORIGINS` | Exact Vercel HTTPS frontend origin(s), comma-separated, no wildcard, no trailing slash (e.g. `https://<app>.vercel.app`). | **NEEDS CONFIGURATION** |
| `CSRF_TRUSTED_ORIGINS` | Only if required by a future cookie/CSRF flow; if used, exact HTTPS origins, comma-separated. Not required for current Bearer-token-only API. | **NEEDS CONFIGURATION** (decision + values if enabled) |
| HTTPS / proxy behavior | Render terminates TLS. Current code: `SECURE_SSL_REDIRECT=False`, `SECURE_PROXY_SSL_HEADER` unset. Verify in dashboard: HTTPS enabled for service/custom domains; do not enable Django SSL redirect until proxy/header behavior is verified. | **NOT VERIFIED** (dashboard/platform verification required) |

## 4. Production database and Supabase

- `DATABASE_URL` must point to the **intended hosted production database** (correct project, correct database, least-privilege role subject to RLS). Do **not** use a superuser/BYPASSRLS role for the API.
- `TEST_DATABASE_URL` must **not** be set on Render. Code uses it only as a local/debug fallback when `DEBUG=true`; production requires `DJANGO_DEBUG=false` and an explicit `DATABASE_URL`, so fallback cannot be used.
- **No migrations have been run** as part of D-02C (and none run in this review). Apply migrations via the approved release process before relying on production data (migration state is **NOT VERIFIED** against any hosted DB in this review).
- JWT/JWKS variables: set `SUPABASE_URL` (and/or explicit `SUPABASE_JWKS_URL`, `SUPABASE_JWT_ISSUER`, `SUPABASE_JWT_AUDIENCE` per project) consistently with the target Supabase project; use asymmetric JWKS when appropriate, or `SUPABASE_JWT_SECRET` only for legacy HS256 (never service-role/secret API keys). Current code derives JWKS/issuer from `SUPABASE_URL` when unset. Configuration values are **NEEDS CONFIGURATION** / verification **NOT VERIFIED**.
- **No Supabase service-role key is needed** by this Django backend (JWT verification uses JWKS or legacy HS256 secret only). Do not place service-role keys in backend env or frontend env.
- Existing RLS policies remain **unchanged** by D-02C (no migration/policy edits). Hosted RLS/grants state is **NOT VERIFIED** in this review.

## 5. Deployment blockers (classified)

### READY
- Repository state for audited files: `main` HEAD `6bb8c73892c718a695e045f23215e2bb2fb62433`; tracked changes limited to D-02C files (`backend/config/settings.py`, `backend/config/tests/test_settings.py`) with no other tracked modifications observed in this review context.
- Django WSGI entrypoint exists (`backend/config/wsgi.py`) and is compatible with `config.wsgi:application`.
- `/health` route and view are correct, unauthenticated, and DB-free.
- Dependency manifest present and pinned (`backend/requirements.txt`) including Gunicorn; D-02C security tests and full backend suite were reported passing in D-02C validation (120 tests). Current tracked test file matches reviewed changes.
- Security code posture (as implemented): middleware order, explicit CSRF trusted origins env, secure cookies gated by DEBUG, SSL redirect/proxy header not enabled, HSTS initial zero, CORS credentials disabled, auth stack unchanged.

### NEEDS CONFIGURATION (manual work before/at service creation)
- Render service settings: Root Directory `backend`, Build Command, Start Command, Health Check Path `/health`, `PYTHON_VERSION=3.14.10`.
- Render environment variables (production): `DJANGO_DEBUG=false`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DATABASE_URL`, `CORS_ALLOWED_ORIGINS`, `SUPABASE_URL` (and any required `SUPABASE_JWKS_URL`/issuer/audience/legacy secret), plus decision on `CSRF_TRUSTED_ORIGINS` if needed. Ensure `TEST_DATABASE_URL` is unset.
- Vercel/frontend: set `NEXT_PUBLIC_API_BASE_URL` to the final API origin (coordinate with Render hostname).
- Supabase/hosted DB prep (operational): confirm target project, JWT strategy, issuer/audience, and that migrations/roles/RLS are prepared per approved process (configuration decisions pending).

### BLOCKED (cannot proceed safely until resolved)
- **Production deployment/release gating from prior reports remains open where stated** (e.g. D-01A listed DR-01 fix/tests/release-commit gates as blocked at the time of that report). D-02D does **not** re-run that gate audit end-to-end beyond reviewing current files; any still-open D-01A gates are **BLOCKED** until completed by authorized owners.
- No approved production domain/origin values are recorded in-repo for final Render/Vercel cutover (exact hostnames/origins must be supplied by owners) — without them, safe configuration of `DJANGO_ALLOWED_HOSTS`/`CORS_ALLOWED_ORIGINS` is **BLOCKED**.

### NOT VERIFIED (requires live/dashboard/hosted checks or execution)
- Render dashboard verification: HTTPS/TLS for service and custom domains, Health Check probe behavior with final `DJANGO_ALLOWED_HOSTS`, actual build/start success on Linux with `PYTHON_VERSION=3.14.10`.
- Whether Render proxies `X-Forwarded-Proto` correctly for enabling `SECURE_PROXY_SSL_HEADER` later (and whether it would be safe).
- Hosted Supabase/JWT: live JWKS reachability, issuer/audience correctness for target project, redirect URL alignment, migration application state, RLS/grants/role restrictions on hosted DB, seeded profile/role presence for live auth.
- Live `/health` and authenticated API smoke tests against the deployed (or pre-deploy validated) service.
- Any end-to-end frontend workflow tests (F1–F4) pending approved browser/E2E driver (per prior reports).

**Distinction (explicit):**
- **Configuration work** = setting Render/Vercel/Supabase env vars and service settings, choosing domains/origins, deciding CSRF/HSTS rollout steps, preparing migration/role plans. These are **NEEDS CONFIGURATION** or **BLOCKED** pending owner decisions.
- **Deployment verification** = proving the service builds/starts on Render Linux, `/health` passes with real host, HTTPS/CORS/auth behave correctly live, hosted DB/RLS/JWT are correct. These are **NOT VERIFIED** until executed in an approved window.

## 6. Deliverable conclusion

**Final recommendation: NOT READY FOR CONFIGURATION**

Rationale (read-only): the code/config changes reviewed (D-02C) are coherent and tests/checks were reported green, but **production-safe Render/Vercel/Supabase configuration values are not yet fixed in an approved form** (no confirmed final API hostnames, no confirmed final Vercel origin(s), no confirmed production JWT/JWKS strategy values set in the target environment, and `PYTHON_VERSION`/service settings not applied). Additionally, critical **deployment verification** items remain **NOT VERIFIED** and prior release gates may still be **BLOCKED**. Until the **NEEDS CONFIGURATION** items are completed with approved values and the **BLOCKED/NOT VERIFIED** items are resolved, the project is **not ready to proceed to configuration-driven deployment execution** beyond planning.

This document is a review only. No files were modified, no services created, no deployments performed, and no hosted systems accessed.