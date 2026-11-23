# D-02A — Final Render Backend Pre-Deployment Verification

Date: 2026-11-23
Task type: read-only backend pre-deployment audit
Repository state audited: `main` at `6bb8c73892c718a695e045f23215e2bb2fb62433`
Target: Render Python web service, root directory `backend`

## 1. Scope and restrictions observed

This was a read-only inspection of repository files, local package metadata, and public vendor documentation.

Not performed:

- No Render service was created, configured, or deployed.
- No source code, configuration, environment file, or dependency manifest was modified.
- No migration was run.
- No hosted database, Supabase project, or production credential was accessed.
- No credential, token, database URL, UUID, email address, phone number, or secret value is reproduced in this report.
- All existing untracked files were preserved.

## 2. Final recommendation

**NOT READY FOR RENDER SERVICE CREATION.**

The repository and application code are in a deployable state: the branch is synchronized, the DR-01 fix and regression tests are committed, the WSGI target and health endpoint exist, the dependency manifest is compatible with the proposed Python runtime, and the application does not require a Supabase service-role key.

However, service creation must wait because mandatory Render and Supabase configuration is still outstanding. In particular, the service cannot start correctly without `DJANGO_SECRET_KEY`, `DATABASE_URL`, and production-safe host/CORS values; the health check will fail unless `DJANGO_ALLOWED_HOSTS` contains the hostname Render uses in the probe; and the JWT/JWKS, migration, RLS, and least-privilege database decisions have not been verified against the target project.

The recommendation becomes **READY FOR RENDER SERVICE CREATION** only after every `NEEDS CONFIGURATION` item in sections 3 and 6 is completed by an authorized owner and the `NOT VERIFIED` items are accepted or verified in the approved deployment window.

## 3. Classification matrix

### 3.1 Git and release state

| ID | Item | Classification | Evidence / required action |
|---|---|---|---|
| G-01 | Branch is `main` | READY | `git status --short --branch` reports `## main...origin/main`. |
| G-02 | Synchronized with `origin/main` | READY | `git rev-list --left-right --count HEAD...refs/remotes/origin/main` reports `0 0`. |
| G-03 | Tracked working tree clean | READY | No staged or unstaged tracked changes were found. |
| G-04 | Untracked files preserved | READY | `backend/b05b7_r.py` remains intentionally untracked and excluded from the deployment artifact. Render builds committed state, so this helper does not affect the service. |
| G-05 | Release commit contains DR-01 fix and tests | READY | HEAD commit is `6bb8c73` (`fix: enforce blood request notes length limit`), including the serializer change, R1–R9 tests, and audit reports. |

### 3.2 Requirements and proposed Python runtime

| ID | Item | Classification | Evidence / required action |
|---|---|---|---|
| P-01 | Dependency manifest exists and is pinned | READY | `backend/requirements.txt` is tracked and pins all runtime dependencies, including Gunicorn. |
| P-02 | Django/Python compatibility | READY | Published metadata for Django 6.1.3 requires Python >= 3.12. The repository comment and README identify Python 3.14 as the intended runtime. |
| P-03 | All pinned packages compatible with Python 3.14.10 | READY | Published `Requires-Python` metadata for every pinned package permits 3.14. Django requires >=3.12; DRF, psycopg, dj-database-url, Gunicorn, and coverage require >=3.10; PyJWT, django-cors-headers, and python-dotenv require >=3.9. |
| P-04 | Proposed Python 3.14.10 exists | READY | Python.org lists 3.14.10 as released on 2026-10-25. |
| P-05 | Render supports proposed Python version | READY | Render's Python version documentation lists 3.14.10 as the current default for services created on or after 2026-11-03 and permits fully qualified `PYTHON_VERSION` values. |
| P-06 | Runtime pinned in repository | NEEDS CONFIGURATION | No `runtime.txt`, `.python-version`, `render.yaml`, or `Procfile` exists. Set Render `PYTHON_VERSION=3.14.10` explicitly; do not rely on the service default. |
| P-07 | Build command supplied to Render | NEEDS CONFIGURATION | Proposed `pip install -r requirements.txt` is valid with Root Directory `backend`, but it has not been configured in Render. |
| P-08 | Dependency install succeeds on Render Linux | NOT VERIFIED | Local evidence is Windows-based with Python 3.14.3. No Render build was executed. |
| P-09 | Local/Linux runtime parity | NOT VERIFIED | Native wheels, import paths, and process startup must be validated on the Linux build image. |

### 3.3 WSGI entry point and Gunicorn start command

| ID | Item | Classification | Evidence / required action |
|---|---|---|---|
| W-01 | WSGI module exists | READY | `backend/config/wsgi.py` exists and sets `DJANGO_SETTINGS_MODULE` to `config.settings`. |
| W-02 | WSGI application object | READY | `config.wsgi:application` exposes the standard Django WSGI callable. |
| W-03 | Root directory resolves module path | READY | With Root Directory `backend`, `config` is a package containing `__init__.py`, so `config.wsgi` is importable. |
| W-04 | Gunicorn dependency | READY | `gunicorn==27.0.1` is pinned in `backend/requirements.txt`. |
| W-05 | Proposed start command shape | READY | `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT` is a conventional WSGI command and uses Render's supplied `PORT`. |
| W-06 | `PORT` handling | READY | `PORT` is supplied by Render; it must not be set manually. |
| W-07 | Linux Gunicorn boot and bind | NOT VERIFIED | The command was not executed on Render Linux. Confirm import, worker startup, and port binding during controlled build validation. |
| W-08 | Static-file collection | NOT VERIFIED | No `STATIC_ROOT`, WhiteNoise, or `collectstatic` build step was found. This is an API-only service, but the owner must explicitly decide whether static collection is required before go-live. |

### 3.4 `/health` endpoint

| ID | Item | Classification | Evidence / required action |
|---|---|---|---|
| H-01 | Route mapping | READY | `backend/config/urls.py` maps `health` to `config.health.HealthView`, which corresponds to `/health`. |
| H-02 | Probe behavior | READY | `HealthView` disables authentication and permissions and returns `{"status": "ok"}` without a database query in the view. |
| H-03 | Render health check path semantics | READY | Render documentation confirms that HTTP checks GET the configured path and accept any 2xx or 3xx response. |
| H-04 | Render probe `Host` header | NEEDS CONFIGURATION | Render uses a verified custom domain, otherwise the service `onrender.com` hostname, as the `Host` header. `DJANGO_ALLOWED_HOSTS` must contain that exact host or Django will return 400 and the health check will fail. |
| H-05 | Live `/health` result on Render | NOT VERIFIED | No live request was made. It depends on H-04 and successful Gunicorn startup. |
| H-06 | Health check path field | NEEDS CONFIGURATION | Set Render Health Check Path to `/health`; no service setting exists yet. |

### 3.5 Production settings audit

| ID | Item | Classification | Evidence / required action |
|---|---|---|---|
| S-01 | `DJANGO_DEBUG=false` | NEEDS CONFIGURATION | Code defaults to false, but the Render value must be set explicitly. Debug mode gates several safety behaviors. |
| S-02 | `DJANGO_SECRET_KEY` | NEEDS CONFIGURATION | `settings.py` raises at startup when debug is false and this value is missing. Supply a strong secret as a Render secret value; never commit it. |
| S-03 | `DJANGO_ALLOWED_HOSTS` | NEEDS CONFIGURATION | Code defaults to local hosts only. Set exact Render/custom API hostnames, comma-separated, with no URL scheme. This affects both normal traffic and H-04. |
| S-04 | `DATABASE_URL` | NEEDS CONFIGURATION | Required when debug is false. Supply the hosted PostgreSQL/Supabase connection URL as a Render secret; use a least-privilege role subject to RLS, not a superuser or privileged role. |
| S-05 | `CORS_ALLOWED_ORIGINS` | NEEDS CONFIGURATION | Code defaults to `http://localhost:3000`. Set the exact HTTPS frontend origin(s), with no trailing slash and no wildcard. |
| S-06 | `SUPABASE_URL` | NEEDS CONFIGURATION | Used to derive the JWKS URL and issuer when explicit overrides are absent. Set the correct target project URL. |
| S-07 | `SUPABASE_JWKS_URL` | NEEDS CONFIGURATION | Derived from `SUPABASE_URL` by default, but the asymmetric key strategy and endpoint reachability must be confirmed. Set explicitly if required by the project. |
| S-08 | `SUPABASE_JWT_ISSUER` | NEEDS CONFIGURATION | Derived from `SUPABASE_URL` by default. Confirm the target project's issuer and override only if it is non-default. |
| S-09 | `SUPABASE_JWT_AUDIENCE` | NEEDS CONFIGURATION | Code defaults to `authenticated`. Confirm the target project's audience and override only if it is non-default. |
| S-10 | `SUPABASE_JWT_SECRET` | NEEDS CONFIGURATION | Required only for legacy HS256 tokens; leave unset when using asymmetric JWKS verification. Never use a service-role or secret API key here. |
| S-11 | Development login denied | READY in code; NOT VERIFIED live | `DevLoginView` rejects requests unless `settings.DEBUG` is true. Confirm denial in a controlled post-deployment check. |
| S-12 | Generic error envelope | READY in code; NOT VERIFIED live | The custom exception handler returns a generic internal-error response for unhandled exceptions. Keep debug disabled so tracebacks are never exposed. |
| S-13 | `.env` handling | READY | `.gitignore` excludes environment files while preserving `.env.example`. `load_dotenv` does not override real environment variables, so Render values take precedence. |

### 3.6 `TEST_DATABASE_URL` safety

| ID | Item | Classification | Evidence / required action |
|---|---|---|---|
| T-01 | Fallback gated by debug mode | READY | `settings.py` uses `TEST_DATABASE_URL` only when `DATABASE_URL` is absent **and** `DJANGO_DEBUG` is true. |
| T-02 | Production debug=false blocks fallback | READY | When debug is false and `DATABASE_URL` is absent, settings raise a `RuntimeError` instead of using `TEST_DATABASE_URL`. |
| T-03 | Explicit `DATABASE_URL` wins | READY | When `DATABASE_URL` is set, it is used regardless of `TEST_DATABASE_URL` or debug mode. |
| T-04 | Test runner not in production path | READY | `DomainSchemaTestRunner` is only used by Django's test command, not by `config.wsgi`, and it rewrites the test connection only when the test runner executes. |
| T-05 | Cannot become production DB under required config | READY | With `DJANGO_DEBUG=false` and an explicit `DATABASE_URL`, the local test URL cannot become the production database. |
| T-06 | Misconfiguration guard | NEEDS CONFIGURATION | Leave `TEST_DATABASE_URL` unset in Render and keep `DJANGO_DEBUG=false`. There is no startup assertion that rejects a hostile `TEST_DATABASE_URL` if someone incorrectly enables debug in production. |
| T-07 | Startup tests for fallback behavior | READY | `backend/config/tests/test_settings.py` covers all four combinations of debug mode and database URL presence/absence. |

### 3.7 HTTPS, CORS, trusted origins, and security settings

| ID | Item | Classification | Evidence / required action |
|---|---|---|---|
| C-01 | CORS allowlist model | READY in code | `CORS_ALLOWED_ORIGINS` is an explicit list from the environment; `CORS_ALLOW_CREDENTIALS=False`; no origin echo or wildcard in code. |
| C-02 | CORS middleware order | READY | `CorsMiddleware` precedes `CommonMiddleware` in `MIDDLEWARE`. |
| C-03 | CSRF / trusted origins | READY in code; NOT VERIFIED live | No Django admin is routed, and DRF uses only `SupabaseJWTAuthentication` with `UNAUTHENTICATED_USER=None`; no `SessionAuthentication` is configured. `CSRF_TRUSTED_ORIGINS` is therefore not required for the API, but verify browser behavior after deployment. |
| C-04 | Django HTTPS hardening settings | NEEDS CONFIGURATION | No `SECURE_SSL_REDIRECT`, `SECURE_PROXY_SSL_HEADER`, `SECURE_HSTS_SECONDS`, `SESSION_COOKIE_SECURE`, or `CSRF_COOKIE_SECURE` settings were found. |
| C-05 | Django security middleware | NEEDS CONFIGURATION | `django.middleware.security.SecurityMiddleware` is not in `MIDDLEWARE`, so Django-level security headers and redirects are not applied. TLS must be enforced at the Render platform layer unless an approved code change adds this middleware. |
| C-06 | Render HTTPS termination | NOT VERIFIED | Platform TLS/certificate state was not accessed. Verify HTTPS is enabled for the service hostname and any custom domain. |
| C-07 | Unknown host rejection | NOT VERIFIED | Depends on correct `DJANGO_ALLOWED_HOSTS`; verify after deployment. |
| C-08 | CORS preflight from final frontend | NOT VERIFIED | Requires the final frontend origin and a controlled browser/preflight test. |

### 3.8 Supabase service-role key

| ID | Item | Classification | Evidence / required action |
|---|---|---|---|
| SR-01 | Application reads no service-role key | READY | No `SUPABASE_SERVICE_ROLE_KEY` or equivalent is read by application code. The only name match in tracked backend code is a log-redaction constant. |
| SR-02 | Service-role key not needed for JWT verification | READY | Tokens are verified locally with JWKS or a legacy HS256 secret; no privileged Supabase API call is made by the backend. |
| SR-03 | Local-only helper contains privileged-role references | READY | `backend/b05b7_r.py` is an untracked local helper and is not part of the committed deployment artifact. It must remain excluded. |
| SR-04 | Database role is least privilege and RLS-bound | NEEDS CONFIGURATION | The API should connect with a restricted role subject to RLS. Confirm the hosted role and grants; do not use a superuser or `BYPASSRLS` role. |

### 3.9 Database and hosted-state verification

| ID | Item | Classification | Evidence / required action |
|---|---|---|---|
| DB-01 | Migration SQL present in repository | READY | SQL migrations and RLS policy files exist under `supabase/`. |
| DB-02 | Hosted migration state | NOT VERIFIED | No hosted database was accessed. Confirm the reviewed migrations are applied to the target project. |
| DB-03 | RLS enabled on domain tables | NOT VERIFIED | Hosted policy state was not accessed. |
| DB-04 | Grants and anon/PUBLIC restrictions | NOT VERIFIED | Hosted grant state was not accessed. |
| DB-05 | Live JWT/JWKS validation | NOT VERIFIED | No live Supabase token was fetched or validated. |
| DB-06 | Live login and redirect configuration | NOT VERIFIED | Hosted Supabase Auth and redirect settings were not accessed. |
| DB-07 | Deploy-time migration strategy | NEEDS CONFIGURATION | No deploy-time migration command exists. Decide whether migrations are applied by the approved release process or by a separately reviewed step; do not silently add `migrate` to web startup. |
| DB-08 | Rollback and smoke-check plan | NEEDS CONFIGURATION | Define the rollback target and post-creation checks for `/health`, one authenticated API call, CORS, dev-login denial, and error behavior. |

## 4. Proposed Render configuration assessment

| Setting | Assessment | Classification |
|---|---|---|
| Root Directory: `backend` | Correct monorepo root for `config.wsgi` and `requirements.txt`. | READY |
| Build Command: `pip install -r requirements.txt` | Valid for the pinned manifest. `python -m pip install -r requirements.txt` is equally acceptable. Must be entered in Render. | NEEDS CONFIGURATION |
| Start Command: `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT` | Correct WSGI target and uses Render's supplied port. Linux execution remains unverified. | READY / NOT VERIFIED |
| Health Check Path: `/health` | Correct path. Will only pass if `DJANGO_ALLOWED_HOSTS` includes the probe's `Host` value. | READY / NEEDS CONFIGURATION |

## 5. No service-role key requirement — conclusion

The Python backend does **not** require a Supabase service-role key, secret API key, or privileged database credential beyond the `DATABASE_URL` connection itself. Authentication is performed by verifying Supabase-issued JWTs with JWKS or a legacy HS256 secret, and roles are resolved from the application profile table rather than trusted from token claims.

The database migration defines database-side roles and grants, but that is schema configuration, not an application credential. The API must connect with a restricted, RLS-subject role.

## 6. Remaining configuration items by platform

### 6.1 Render

| ID | Item | Classification |
|---|---|---|
| R-01 | Create Python web service from `main` at the approved SHA | NEEDS CONFIGURATION |
| R-02 | Set Root Directory to `backend` | NEEDS CONFIGURATION |
| R-03 | Set Build Command | NEEDS CONFIGURATION |
| R-04 | Set Start Command | NEEDS CONFIGURATION |
| R-05 | Set Health Check Path to `/health` | NEEDS CONFIGURATION |
| R-06 | Set `PYTHON_VERSION=3.14.10` | NEEDS CONFIGURATION |
| R-07 | Set `DJANGO_DEBUG=false` | NEEDS CONFIGURATION |
| R-08 | Set `DJANGO_SECRET_KEY` as a secret | NEEDS CONFIGURATION |
| R-09 | Set `DJANGO_ALLOWED_HOSTS` with the exact probe/custom hostnames | NEEDS CONFIGURATION |
| R-10 | Set `DATABASE_URL` as a secret, using a least-privilege role | NEEDS CONFIGURATION |
| R-11 | Set `CORS_ALLOWED_ORIGINS` to the exact HTTPS frontend origin(s) | NEEDS CONFIGURATION |
| R-12 | Set `SUPABASE_URL` | NEEDS CONFIGURATION |
| R-13 | Set or confirm `SUPABASE_JWKS_URL` | NEEDS CONFIGURATION |
| R-14 | Set or confirm `SUPABASE_JWT_ISSUER` | NEEDS CONFIGURATION |
| R-15 | Set or confirm `SUPABASE_JWT_AUDIENCE` | NEEDS CONFIGURATION |
| R-16 | Set `SUPABASE_JWT_SECRET` only for legacy HS256; otherwise leave unset | NEEDS CONFIGURATION |
| R-17 | Leave `TEST_DATABASE_URL` unset | NEEDS CONFIGURATION |
| R-18 | Do not set `PORT` manually | READY |
| R-19 | Select region, plan, instances, and custom domain | NEEDS CONFIGURATION |
| R-20 | Decide Auto Deploy policy after branch/commit approval | NEEDS CONFIGURATION |
| R-21 | Verify HTTPS/TLS for service and custom domains | NOT VERIFIED |
| R-22 | Validate Linux build, Gunicorn startup, and `/health` in a controlled window | NOT VERIFIED |

### 6.2 Supabase / hosted database

| ID | Item | Classification |
|---|---|---|
| SB-01 | Confirm correct target project URL | NEEDS CONFIGURATION |
| SB-02 | Choose asymmetric JWKS or legacy HS256 key strategy | NEEDS CONFIGURATION |
| SB-03 | Confirm JWKS reachability and key rotation behavior | NOT VERIFIED |
| SB-04 | Confirm issuer and audience values | NEEDS CONFIGURATION |
| SB-05 | Confirm redirect URLs use the final HTTPS frontend origin | NOT VERIFIED |
| SB-06 | Confirm migrations 0001–0010 are applied | NOT VERIFIED |
| SB-07 | Confirm RLS, grants, and anon/PUBLIC restrictions in hosted state | NOT VERIFIED |
| SB-08 | Confirm API database role is restricted and RLS-bound | NEEDS CONFIGURATION |
| SB-09 | Confirm seeded profile/role records needed for live authentication | NOT VERIFIED |
| SB-10 | Use only public/publishable keys in frontend configuration | NEEDS CONFIGURATION |

## 7. Items deliberately not verified

The following remain outside this read-only backend audit:

- Live Render service creation, build, startup, or health check.
- Live Supabase token issuance, JWKS fetch, RLS enforcement, or redirect behavior.
- Frontend/Vercel configuration and browser workflow tests F1–F4.
- Production database connectivity using real credentials.
- Exact environment variable values; only variable names and control flow were reviewed.

## 8. Conditions required to change the recommendation to READY

1. Complete every `NEEDS CONFIGURATION` item in sections 3 and 6, especially environment values, exact hosts/origins, Python pin, health check path, and the database role decision.
2. Confirm the Linux build and Gunicorn start command in a controlled validation.
3. Verify the live `/health` response with the final `DJANGO_ALLOWED_HOSTS`.
4. Verify hosted Supabase JWT/JWKS, issuer/audience, redirects, migrations, RLS, and grants.
5. Accept or complete the `NOT VERIFIED` items in a documented go-live window.

Until those conditions are met, creating the Render service would be expected to fail at startup or health checking rather than produce a usable deployment.

## 9. Verification statement

- No source, configuration, dependency, environment, or database change was made.
- No Render or Supabase resource was created or modified.
- No secret value, credential, token, database URL, UUID, email address, or phone number is reproduced in this report.
- The repository remains on `main`, synchronized with `origin/main`, with the same preserved untracked local helper.
