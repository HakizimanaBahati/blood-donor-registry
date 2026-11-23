# D-02E — Render Configuration Blocker Analysis

Date: 2026-11-23  
Source: `docs/D-02D_RENDER_CONFIGURATION_REVIEW.md` (read-only analysis)  
Scope: Backend (Django) on Render, Vercel frontend coordination, Supabase auth/DB configuration decisions. No code/config changes, no hosted access, no deployments.

## 1. Items classified as BLOCKED (from D-02D)

1. **Prior release/deployment gates (D-01A lineage) still open where stated**
- What is missing: Confirmation that all D-01A release gates (including DR-01 fix/tests/release-commit decisions and any other gates marked blocked at the time of D-01A) are completed and recorded by authorized owners.
- Why it matters: Deploying while a known release gate is open risks shipping known defects or an unproven release state.
- Action type: **Code change and/or repo/release process decision** (owned by authorized maintainers), not a Render/Supabase dashboard toggle.
- Safest way to resolve: Complete the specific D-01A gate checklist items in a controlled branch/workflow, record results in the appropriate report/commit notes, and only then proceed to Render configuration.

2. **No approved production domain/origin values recorded for final cutover**
- What is missing: Final, approved values for (a) exact Render API hostname(s) (service and any custom domain) and (b) exact canonical Vercel HTTPS origin(s) (apex/www and production vs preview policy). Also no approved decision recorded for whether `CSRF_TRUSTED_ORIGINS` is required at launch.
- Why it matters: `DJANGO_ALLOWED_HOSTS` and `CORS_ALLOWED_ORIGINS` cannot be safely set without exact values; wrong or missing values cause 400s, blocked CORS, or insecure/wildcard drift. `CSRF_TRUSTED_ORIGINS` set incorrectly (or needed but unset) creates avoidable security/behavior risk later.
- Action type: **Verified deployment domain / owner decision** (business/product + infra owners). May later require **Render dashboard** and **Vercel dashboard** entries, but the *values* must be approved first.
- Safest way to resolve: Obtain written/recorded approval of exact domains/origins (placeholders in docs are not sufficient). Document the canonical list (no wildcards, no trailing slashes, HTTPS only for frontend). Decide explicitly whether `CSRF_TRUSTED_ORIGINS` is needed now (current Bearer-token API: typically no) and record that decision.

## 2. Items classified as NEEDS CONFIGURATION (from D-02D)

### Render service settings (dashboard / IaC)
1. **Root Directory = `backend`**
- Missing: Not set/confirmed in the Render service configuration.
- Why it matters: Wrong root breaks imports (`config.wsgi`) and dependency install path.
- Action type: **Render dashboard** (or IaC).
- Safest resolution: Set Root Directory to `backend`; verify from a test deploy context conceptually (no deploy here). This is a service-setting field, not code.

2. **Build Command**
- Missing: Not configured (e.g. `pip install -r requirements.txt` or `python -m pip install -r requirements.txt`).
- Why it matters: Without it, dependencies may not install consistently.
- Action type: **Render dashboard** (or IaC).
- Safest resolution: Set Build Command to `pip install -r requirements.txt` (run in `backend` root). Keep it minimal and pinned manifest-driven.

3. **Start Command**
- Missing: Not configured (`gunicorn config.wsgi:application --bind 0.0.0.0:$PORT`).
- Why it matters: Service will not start the correct WSGI app with correct binding.
- Action type: **Render dashboard** (or IaC).
- Safest resolution: Set exactly to `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT`; do not set `PORT` manually.

4. **Health Check Path = `/health`**
- Missing: Not configured in Render.
- Why it matters: Health checks must target the implemented unauthenticated endpoint.
- Action type: **Render dashboard** (or IaC).
- Safest resolution: Set Health Check Path to `/health`. Ensure `DJANGO_ALLOWED_HOSTS` includes the probe host (see below).

5. **`PYTHON_VERSION=3.14.10`**
- Missing: No repo pin file; Render env var not set.
- Why it matters: Avoids runtime drift from defaults and matches reviewed compatibility assumptions.
- Action type: **Render dashboard** (env var).
- Safest resolution: Set `PYTHON_VERSION=3.14.10` explicitly on the Render service.

### Render environment variables (production)
6. **`DJANGO_DEBUG=false`**
- Missing: Not set for production service.
- Why it matters: Enables production guards (secret key required, test DB fallback blocked behavior in practice), secure cookie flags, safer logging.
- Action type: **Render dashboard** (env var).
- Safest resolution: Set to `false`.

7. **`DJANGO_SECRET_KEY`**
- Missing: Not set (must be strong random secret in secret store).
- Why it matters: Required when `DEBUG=false`; startup fails without it.
- Action type: **Render dashboard** (secret env var).
- Safest resolution: Generate a strong secret out of band and store only in Render secrets; never commit.

8. **`DJANGO_ALLOWED_HOSTS`**
- Missing: Final exact host list not set/approved.
- Why it matters: Wrong/missing hosts cause 400 (including failed health probes) or over-broad acceptance.
- Action type: **Render dashboard** (env var) using **verified deployment domain(s)** approved by owners.
- Safest resolution: After domain approval, set comma-separated exact hosts (no scheme), including Render service hostname(s) and any custom API domain(s) used by clients and probes.

9. **`DATABASE_URL`**
- Missing: Production connection string not set (must point to intended hosted DB, least-privilege RLS-bound role).
- Why it matters: API cannot run correctly/security posture depends on correct role/RLS; wrong DB is a critical risk.
- Action type: **Render dashboard** (secret env var) informed by **Supabase/DB provisioning decisions** (owner-approved).
- Safest resolution: Set only after confirming target project/role and RLS plan; use secret storage; never log or print values.

10. **`CORS_ALLOWED_ORIGINS`**
- Missing: Final exact Vercel HTTPS origin(s) not set/approved.
- Why it matters: Blocks legitimate frontend calls or allows unintended origins if mis-set.
- Action type: **Render dashboard** (env var) using **verified deployment domain(s)** from Vercel.
- Safest resolution: Set exact HTTPS origins only (no wildcard, no trailing slash), matching approved production frontend canonical URL(s).

11. **`SUPABASE_URL` (and related JWT vars as needed)**
- Missing: Production values/strategy not finalized in the deployed environment (may need `SUPABASE_JWKS_URL`, `SUPABASE_JWT_ISSUER`, `SUPABASE_JWT_AUDIENCE`, or legacy `SUPABASE_JWT_SECRET` only if required).
- Why it matters: JWT verification fails or is misconfigured without correct project URL/keys strategy.
- Action type: **Render dashboard** (env/secrets) guided by **Supabase dashboard/project configuration** decisions.
- Safest resolution: Choose JWKS vs legacy HS256 explicitly (prefer JWKS), set `SUPABASE_URL` and overrides only if non-default; never use service-role/secret API keys.

12. **`CSRF_TRUSTED_ORIGINS` (decision + value if enabled)**
- Missing: Decision recorded? If enabled, values not set.
- Why it matters: Only relevant if Django CSRF/cookie flows are introduced; current Bearer-token API typically does not need it, but leaving ambiguous is risky if behavior changes.
- Action type: **Owner decision**, then **Render dashboard** (env var) if enabled (using verified HTTPS origins).
- Safest resolution: Record decision “not required at launch” unless a concrete cookie/CSRF flow exists; if required later, set explicit HTTPS origins only.

13. **Ensure `TEST_DATABASE_URL` is unset on Render**
- Missing: Must be verified absent in Render env.
- Why it matters: Prevents accidental use of a test/local-style DB URL in any misconfigured scenario (code guards exist but defense in depth is good).
- Action type: **Render dashboard** (env var review/removal).
- Safest resolution: Confirm not present; document as a deployment checklist item.

### Vercel / frontend coordination
14. **`NEXT_PUBLIC_API_BASE_URL` (frontend) set to final API origin**
- Missing: Not coordinated to final Render/custom API URL.
- Why it matters: Frontend cannot reach API; CORS/host alignment depends on this.
- Action type: **Vercel dashboard** (env var) using **verified deployment domain**.
- Safest resolution: Set to the exact HTTPS API origin after Render hostname is known/approved; keep in sync with `CORS_ALLOWED_ORIGINS`.

### Supabase / hosted DB operational prep (decisions)
15. **Target project/JWT strategy and operational readiness decisions**
- Missing: Final confirmation of target Supabase project, JWT strategy (JWKS/legacy), issuer/audience expectations, migration application plan, role/RLS posture plan (least privilege, RLS-bound API role), redirect URL alignment considerations for frontend auth flow.
- Why it matters: Authentication and data access correctness/security depend on these; misconfiguration causes auth failures or unsafe access patterns.
- Action type: **Supabase dashboard / DB operations (approved process)** plus owner decisions.
- Safest resolution: Complete an approved pre-deploy checklist in Supabase (project selection, JWT settings documented, migration plan, role grants/RLS verified by process) without exposing secrets in docs.

## 3. Items classified as NOT VERIFIED (from D-02D)

1. **Render dashboard/platform verification**
- Missing verification: HTTPS/TLS enabled for service and custom domains; Health Check behavior with final `DJANGO_ALLOWED_HOSTS`; actual Linux build/start success with `PYTHON_VERSION=3.14.10`.
- Why it matters: These are runtime/platform facts that code review cannot guarantee.
- Action type: **Render dashboard** checks + **deployment verification** run in an approved window (after configuration).
- Safest resolution: After service exists with correct config, verify TLS, set/confirm health path, observe first deploy logs/build, confirm `/health` returns 200 with correct Host behavior.

2. **Render proxy forwarded headers (`X-Forwarded-Proto`) safety**
- Missing verification: Whether Render reliably forwards and sanitizes `X-Forwarded-Proto` (or equivalent) such that enabling `SECURE_PROXY_SSL_HEADER` would be safe.
- Why it matters: Trusting spoofable headers can mislead Django about scheme/security.
- Action type: **Deployment verification** (inspect headers in controlled test) plus **Render behavior verification**.
- Safest resolution: Keep `SECURE_PROXY_SSL_HEADER` unset until verified; if later enabled, do so only after documented proof and keep `SECURE_SSL_REDIRECT` behavior carefully tested (currently off).

3. **Hosted Supabase/JWT live verification**
- Missing verification: Live JWKS reachability, issuer/audience correctness for target project, redirect URL alignment, migration application state, RLS/grants/role restrictions on hosted DB, seeded profile/role presence for live auth.
- Why it matters: Auth and data isolation can fail silently or insecurely if any of these are wrong.
- Action type: **Supabase dashboard / hosted DB verification** via approved tooling/process (no direct DB credential dumping into docs).
- Safest resolution: Run a documented verification checklist against the target project (read-only checks where possible), confirm migrations applied and RLS/grants enforced for the API role, then test with controlled auth flows.

4. **Live API smoke tests**
- Missing verification: `/health` and authenticated API smoke tests against deployed (or pre-deploy validated) service.
- Why it matters: Confirms end-to-end wiring (host, CORS, JWT, DB role/RLS interactions at runtime).
- Action type: **Deployment verification**.
- Safest resolution: After deploy, call `/health` from allowed contexts and perform minimal authenticated requests using approved test accounts/tokens in a safe environment.

5. **Frontend E2E workflow tests (F1–F4)**
- Missing verification: Browser/E2E flows pending approved driver (per prior reports).
- Why it matters: User-facing flows may break due to CORS, auth redirect, or API changes even if unit/integration tests pass.
- Action type: **Deployment verification** (after frontend is configured/deployed to approved target).
- Safest resolution: Execute approved E2E suite against staging/production-like targets once drivers and environments are ready.

## 4. Tasks that can be completed BEFORE creating a Render service (pre-service)

These do **not** require an existing Render web service instance to be created:

- Obtain and record approved production values: exact API hostnames (planned), exact Vercel HTTPS origins, and `CSRF_TRUSTED_ORIGINS` decision (with values if any).
- Decide JWT strategy for target Supabase project (JWKS vs legacy HS256) and document required env var names/behavior (values stored later in Render/Supabase as appropriate).
- Prepare Supabase/DB operational plan (approved): confirm target project, migration application order/process, least-privilege RLS-bound API role and grants design, redirect URL expectations (documented decisions), and a verification checklist (to be executed later).
- Draft the exact Render service settings and env var list (names + placeholder formats) for copy/paste into Render once service is created (no secrets in repo).
- Confirm local/test hygiene: ensure `TEST_DATABASE_URL` remains unset in any production env plans; ensure no secrets in committed files.
- Resolve any remaining **BLOCKED** owner/decision items (D-01A gate closure, domain/origin approvals) so configuration is unambiguous.

## 5. Tasks that REQUIRE an actual Render service (post-service / during/after creation)

These require a Render service to exist (or to be in the process of being created/configured in the dashboard):

- Set Render service settings in the dashboard/IaC: Root Directory `backend`, Build Command, Start Command, Health Check Path `/health`, `PYTHON_VERSION=3.14.10`.
- Set Render environment variables in the dashboard: `DJANGO_DEBUG`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DATABASE_URL`, `CORS_ALLOWED_ORIGINS`, `SUPABASE_*` vars, `CSRF_TRUSTED_ORIGINS` (if used), and verify `TEST_DATABASE_URL` absent.
- Perform Render dashboard/platform verification: HTTPS/TLS state, build/start logs on Linux, health probe behavior against `/health` with real host.
- Verify proxy header behavior (`X-Forwarded-Proto`) in a controlled request inspection once the service is reachable.
- Run live smoke tests: `/health`, authenticated API calls, CORS checks from the approved frontend origin(s).
- Coordinate Vercel env (`NEXT_PUBLIC_API_BASE_URL`) to the actual API hostname after it is known, then validate frontend/API integration.
- Execute post-deploy hosted verifications that depend on the running service context (e.g. end-to-end auth flows) and any approved E2E suite once environments are ready.

## 6. Recommended next three actions (priority order)

1. **Close BLOCKED owner/decision items first (pre-service, highest priority).** Obtain written/recorded approval of exact production API hostnames and exact canonical Vercel HTTPS origins (and policy for previews if any), plus a recorded decision on `CSRF_TRUSTED_ORIGINS` at launch. Until these are fixed, `DJANGO_ALLOWED_HOSTS`/`CORS_ALLOWED_ORIGINS` cannot be set safely.
2. **Finalize Supabase/JWT and DB operational decisions (pre-service).** Choose JWKS vs legacy HS256 for the target project, confirm issuer/audience expectations, and prepare an approved migration/role/RLS verification plan (least-privilege RLS-bound API role). Record these decisions so Render env vars and deployment steps are unambiguous.
3. **Create/configure the Render service only after (1)–(2), then verify (post-service).** Set the service settings and env vars from the approved list, deploy to a controlled environment, verify HTTPS/TLS, health checks, logs, `/health`, and minimal authenticated+CORS behavior before broader rollout or E2E testing.

## 7. Notes (constraints reiterated)

- This analysis is read-only. No source code, environment files, databases, services, or deployments were modified or accessed.
- No secrets, credentials, tokens, UUIDs, or database URLs are included here; use platform secret stores and approved private channels for real values.
- `CSRF_TRUSTED_ORIGINS` should remain unset unless a concrete cookie/CSRF flow is required at launch.