# D-03A — Production Domain and Supabase Configuration Audit

Date: 2026-11-23  
Task type: read-only audit (no service creation, no env file changes, no hosted DB/data access, no migrations, no Supabase changes, no commits/pushes)  
Approved domain decisions (for planning): Render-generated `*.onrender.com` API domain; Vercel-generated `*.vercel.app` frontend domain; no custom domains; prefer Supabase JWKS-based JWT verification; retain existing Supabase PostgreSQL project and RLS.

## 1. Scope and method (what was reviewed)

Reviewed (repository and prior reports), read-only:
- Backend: `backend/config/settings.py`, `backend/config/urls.py`, `backend/config/health.py`, `backend/config/wsgi.py`, `backend/config/test_runner.py`, `backend/requirements.txt`, `backend/.env.example`
- Auth/JWT/RLS application layer: `backend/authentication/jwt.py`, `backend/authentication/authentication.py`, `backend/authentication/middleware.py`, `backend/authentication/permissions.py`, `backend/authentication/views.py`, `backend/authentication/services.py` (referenced behavior), `backend/common/errors.py` (context)
- Frontend: `frontend/lib/supabase.ts`, `frontend/lib/api.ts` (usage context), `frontend/.env.example`, `frontend/next.config.ts`, `README.md` excerpts
- Supabase migrations (RLS/grants/function hardening context): `supabase/migrations/0005_rls.sql`, `0009_harden_function_search_paths.sql`, `0010_revoke_rls_auto_enable.sql` (and listing reviewed)
- Prior reports: `docs/D-01_DEPLOYMENT_READINESS_REPORT.md`, `docs/D-02A_RENDER_PREDEPLOYMENT_REPORT.md`, `docs/D-02D_RENDER_CONFIGURATION_REVIEW.md`, `docs/D-02E_BLOCKER_ANALYSIS.md`, `docs/PRODUCTION_READINESS_REPORT.md`, `docs/SUPABASE_SETUP.md`, `README.md`

Not performed: no Render/Vercel/Supabase dashboard changes or service creation; no live HTTP/JWT/DB verification beyond static inspection; no secrets printed or recorded.

## 2. Classification summary

Findings are classified as: **READY**, **NEEDS CONFIGURATION**, **BLOCKED**, **NOT VERIFIED**.

| Area | Summary |
|---|---|
| Backend JWT verification (code) | **READY** (behavior documented below); live project correctness **NOT VERIFIED** |
| Backend env wiring for Supabase/JWT | **NEEDS CONFIGURATION** (values/strategy must be set per target project) |
| CORS/hosts/CSRF after platform domains | **NEEDS CONFIGURATION** (exact final origins/hosts required) + **BLOCKED** until final domains approved/known in practice |
| Frontend env for Vercel (`*.vercel.app`) + API origin | **NEEDS CONFIGURATION** |
| Supabase Auth redirects (hosted) | **NOT VERIFIED** (must be configured/confirmed in Supabase Dashboard) |
| Database connection strategy (least privilege + RLS) | **NEEDS CONFIGURATION** / operational decisions **BLOCKED** until role plan approved; hosted state **NOT VERIFIED** |
| RLS policies (repo evidence) | **READY** (migrations present); hosted enforcement/grants **NOT VERIFIED** |
| Vercel Hobby plan suitability | **NEEDS CONFIGURATION** (plan constraints/fit must be confirmed by owner; not auto-“OK”) |

## 3. Current Supabase URL / JWKS / issuer / audience configuration (code review, no secrets)

### 3.1 Environment inputs (backend, `backend/config/settings.py`)
- `SUPABASE_URL` = `os.getenv("SUPABASE_URL", "").rstrip("/")` (empty string if unset).
- `SUPABASE_JWT_SECRET` = stripped env (empty if unset). In **DEBUG** only, if neither a secret nor a JWKS URL is effectively configured for production-like asymmetric use, code sets a development-only fallback secret (clearly marked in comments). **Production** (`DJANGO_DEBUG=false`) requires real config via env; no fallback secret is applied in that path.
- `SUPABASE_JWKS_URL` = env or empty; if `SUPABASE_URL` set and `SUPABASE_JWKS_URL` empty, derived as: **`{SUPABASE_URL}/auth/v1/.well-known/jwks.json`**.
- `SUPABASE_JWT_ISSUER` = env or empty; if `SUPABASE_URL` set and `SUPABASE_JWT_ISSUER` empty, derived as: **`{SUPABASE_URL}/auth/v1`**.
- `SUPABASE_JWT_AUDIENCE` = env or `"authenticated"` (stripped). Default is **`authenticated`**.
- `JWT_ALGORITHMS = ("HS256","RS256","ES256")`.

### 3.2 Verification behavior (`backend/authentication/jwt.py`)
- Reads unverified header to obtain `alg` and presence of `kid` (for diagnostics only; logs are sanitized). Rejects if `alg` not in `JWT_ALGORITHMS`, rejects `alg == "none"`, requires `exp`, `sub`, `iat` (enforced via PyJWT `options.require`). Verifies signature, expiry, audience, issuer.
- **HS256**: requires `SUPABASE_JWT_SECRET` set; decodes with that secret.
- **Asymmetric (RS256/ES256, etc. per algorithms tuple)**: uses `PyJWKClient` against `settings.SUPABASE_JWKS_URL` (cached), fetches signing key from JWT (`get_signing_key_from_jwt`). If JWKS URL/config missing for asymmetric path, verification fails with a generic temporary/unavailable-style error category in code paths that catch retrieval issues (message surfaced to API is sanitized/generic).
- On success returns `VerifiedToken(subject=<uuid string>, claims=...)`; `sub` must parse as a valid UUID or verification fails.
- Middleware (`authentication.middleware.SupabaseClaimsMiddleware`) calls `verify_access_token` for Bearer tokens and sets RLS session variables (`request.jwt.claim.sub`, `request.jwt.claim.role='authenticated'`, sets local role `authenticated`) inside a transaction when a verified token exists; DRF authentication (`SupabaseJWTAuthentication`) reuses `request.verified_token` when present or verifies again, then resolves a local app user from `profiles` by `sub`. Role/authorization is taken from the local profile, not from arbitrary JWT claims trusted for app roles (per code/comments and prior reports).

### 3.3 Exact issuer and JWKS URL formats expected by this codebase (as written)
- **JWKS URL (derived default):** `https://<SUPABASE_PROJECT_REF>.supabase.co/auth/v1/.well-known/jwks.json`  
  - Code sets `SUPABASE_JWKS_URL = SUPABASE_JWKS_URL or f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"` when `SUPABASE_URL` is non-empty.
- **Issuer (derived default):** `https://<SUPABASE_PROJECT_REF>.supabase.co/auth/v1`  
  - Code sets `SUPABASE_JWT_ISSUER = SUPABASE_JWT_ISSUER or f"{SUPABASE_URL}/auth/v1"`.
- **Audience:** default `authenticated` unless `SUPABASE_JWT_AUDIENCE` overrides it.
- **Important:** The code does **not** enforce a project-ref pattern beyond using whatever `SUPABASE_URL`/overrides you provide; correctness depends on matching the **actual** Supabase Auth issuer and JWKS published by the target project (confirm in Dashboard / observed tokens). This is **NOT VERIFIED** live here.

### 3.4 What “prefer JWKS-based (asymmetric) verification” means operationally (this repo)
- Preferred path in code: **do not set** `SUPABASE_JWT_SECRET` for normal operation when the project issues RS256/ES256 tokens; ensure `SUPABASE_URL` is set so JWKS/issuer defaults apply (or set `SUPABASE_JWKS_URL`/`SUPABASE_JWT_ISSUER` explicitly if your project differs). `JWT_ALGORITHMS` already allow RS256/ES256/HS256.
- Legacy HS256 remains supported only if `SUPABASE_JWT_SECRET` is configured; do **not** substitute a Supabase service/secret API key for this value.

## 4. Manual confirmations required in the Supabase Dashboard (no changes made here)

The following must be **verified/configured manually** in the target Supabase project (names/descriptions only; no secrets recorded):
1. **Project URL** matches `SUPABASE_URL` used by the backend (same host as the project’s Auth base URL).
2. **Signing keys / JWT strategy**: confirm whether tokens are signed with **asymmetric keys (JWKS)** or legacy **HS256** secret; align backend env accordingly (prefer JWKS). If using JWKS, confirm the published JWKS endpoint is reachable from the internet/network path Render uses (operational **NOT VERIFIED** until tested).
3. **JWT issuer and audience**: confirm the `iss` and `aud` claims emitted by Auth for the environment you deploy to; if they differ from defaults (`…/auth/v1`, `authenticated`), set `SUPABASE_JWT_ISSUER` / `SUPABASE_JWT_AUDIENCE` explicitly on Render.
4. **Auth providers and email/password** behavior as needed (existing project retained); confirm admin/hospital user provisioning approach still matches `public.profiles` and `assign_role`/app expectations (see RLS notes).
5. **Redirect URLs / allowed redirect URLs** (see Section 7): add the final Vercel frontend origins used for password recovery and any auth callback flows the app uses.
6. **Database**: confirm you are using the intended existing PostgreSQL project; confirm API connection uses a **non-superuser, RLS-bound role** (see Section 8). Hosted migration/RLS/grant state **NOT VERIFIED** here.
7. **Keys exposure rule (operational):** frontend must use only **public/publishable** Supabase keys (`NEXT_PUBLIC_SUPABASE_URL` + publishable/anon public key). Never place `sb_secret_...`, service-role, JWT secret, or `DATABASE_URL` in Vercel/frontend env or repo.

## 5. Frontend and backend environment variable requirements (production planning)

### 5.1 Backend (Render) — required/expected (from code + reports)
Set in Render (secrets where sensitive). Placeholders only:
- `DJANGO_DEBUG=false`
- `DJANGO_SECRET_KEY` (**secret**) — required when debug false.
- `DJANGO_ALLOWED_HOSTS` — comma-separated exact hostnames, no scheme (must include the Render service hostname and any custom API hostname; **must include the host Render uses for health probes**).
- `DATABASE_URL` (**secret**) — hosted Postgres URL for the API; least-privilege, RLS-bound role (not superuser/BYPASSRLS).
- `CORS_ALLOWED_ORIGINS` — comma-separated exact HTTPS frontend origin(s), no wildcard, no trailing slash.
- `SUPABASE_URL` — project URL (enables derived JWKS/issuer defaults if overrides unset).
- `SUPABASE_JWKS_URL` / `SUPABASE_JWT_ISSUER` / `SUPABASE_JWT_AUDIENCE` — set only if different from defaults or for explicit control.
- `SUPABASE_JWT_SECRET` — **only** for legacy HS256; otherwise unset. Never a service-role key.
- Optional/future: `CSRF_TRUSTED_ORIGINS` — only if a cookie/CSRF flow is introduced (current Bearer-token API typically does not require it).
- `PYTHON_VERSION=3.14.10` (recommended; no repo pin file). `PORT` supplied by Render (do not set manually).
- **Do not set** `TEST_DATABASE_URL` on Render.

### 5.2 Frontend (Vercel) — required
From `frontend/.env.example`, `frontend/lib/supabase.ts`, and README:
- `NEXT_PUBLIC_SUPABASE_URL` — target Supabase project URL (public).
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` and/or `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` — public/publishable key only (support both names in code). Do **not** use secret keys.
- `NEXT_PUBLIC_API_BASE_URL` — exact HTTPS backend API origin, no trailing slash (must match what the browser calls and what backend CORS allows).
- `NEXT_PUBLIC_ALLOW_DEV_LOGIN` — **false** or unset in Production (development/demo login path is gated server-side by `DJANGO_DEBUG`, but the frontend flag must not be enabled in production).

### 5.3 Backend `.env.example` notes (for operators)
`backend/.env.example` documents `DATABASE_URL`, `SUPABASE_URL`, optional `SUPABASE_JWT_SECRET`/JWKS/issuer/audience, `CORS_ALLOWED_ORIGINS`, `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `TEST_DATABASE_URL` (local only). This audit does not change it; values above are the production checklist.

## 6. Exact CORS and ALLOWED_HOSTS configuration after platform domains are assigned (approved decisions applied)

### 6.1 Approved domain assumptions (from this task)
- Backend API on **Render-generated `*.onrender.com`** (no custom domain purchase). Example shape only: `https://<service-name>.onrender.com`.
- Frontend on **Vercel-generated `*.vercel.app`** (no custom domain purchase). Example shape only: `https://<project-or-branch>.vercel.app` depending on your canonical URL strategy (apex/project default vs preview URLs — see below).

### 6.2 Backend `DJANGO_ALLOWED_HOSTS` (Render)
- Source: comma-separated list from `DJANGO_ALLOWED_HOSTS` (no scheme). Code default is local-only; production must set explicitly.
- **Required (minimum, typical):** include the exact Render service hostname, e.g.  
  `DJANGO_ALLOWED_HOSTS=<service-name>.onrender.com`
- If you use any additional **API** custom-like host not applicable here, omit; with `*.onrender.com` only, that single host is the baseline **unless** Render’s health probe or internal routing uses a different Host in some cases — **must include the host used by Render health checks/probes** (commonly the service `.onrender.com` hostname). This remains **NOT VERIFIED** until a live probe is observed, but the safe rule is: **set `DJANGO_ALLOWED_HOSTS` to the exact hostname(s) clients and Render probes use**.
- Do **not** add wildcards in production intent without careful review; prefer exact hostnames.

### 6.3 Backend `CORS_ALLOWED_ORIGINS` (Render)
- Source: comma-separated list from `CORS_ALLOWED_ORIGINS`; code sets `CORS_ALLOW_CREDENTIALS=False`, no wildcard in code.
- **Canonical production frontend:** set to the exact HTTPS Vercel origin(s) you approve, e.g.  
  `CORS_ALLOWED_ORIGINS=https://<your-app>.vercel.app`
- Rules (from code/reports): **exact HTTPS origins**, **no trailing slash**, **no wildcard**. If you need multiple origins (e.g. production `*.vercel.app` project URL plus a specific preview URL you explicitly allow), list each explicitly and separately — but broad preview allowance is risky; prefer restricting to known origins.
- **Preview deployments:** Vercel preview URLs are often unique per deployment/branch patterns; allowing arbitrary previews is operationally noisy/insecure. Recommended policy (decision): either (a) do **not** allow previews against production API in the same allowlist without approval, or (b) explicitly add only the specific preview origin(s) you test, then remove. This is a **NEEDS CONFIGURATION / owner decision** item.

### 6.4 Backend `CSRF_TRUSTED_ORIGINS` (Render)
- Parsed only from `CSRF_TRUSTED_ORIGINS` (explicit), not derived from CORS; no hardcoded domains. Current API uses Bearer tokens with DRF’s configured authentication and no session auth in REST_FRAMEWORK defaults shown — **typically not required at launch**.
- If ever required, set to exact HTTPS origins matching the frontend(s), e.g. `https://<your-app>.vercel.app`, comma-separated. Default should remain **unset/empty** unless a concrete cookie/CSRF flow is introduced.

### 6.5 HTTPS and proxy notes (relevant to “after domains assigned”)
- Render terminates TLS for `*.onrender.com` (and custom domains). Code currently sets `SECURE_SSL_REDIRECT=False` and does **not** set `SECURE_PROXY_SSL_HEADER`. Do **not** enable Django SSL redirect or trust forwarded proto until proxy behavior is verified (**NOT VERIFIED**). The platform should serve HTTPS; clients should use `https://` API URLs.

### 6.6 Quick “fill-in” template (placeholders only — replace with real approved values)
- `DJANGO_ALLOWED_HOSTS=<render-service>.onrender.com`
- `CORS_ALLOWED_ORIGINS=https://<vercel-app>.vercel.app`
- `NEXT_PUBLIC_API_BASE_URL=https://<render-service>.onrender.com`
- `NEXT_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co` (+ public key vars)

**Status:** template is **READY as a pattern**; real values are **NEEDS CONFIGURATION** and final confirmation is **NOT VERIFIED** until domains are provisioned/observed and approved.

## 7. Supabase Auth redirect URLs and allowed redirect configuration (hosted, not changed here)

From repo/docs context (`README.md`, `docs/D-01_DEPLOYMENT_READINESS_REPORT.md`, `docs/D-02D_RENDER_CONFIGURATION_REVIEW.md`, `frontend/lib/supabase.ts` uses Supabase Auth client with `detectSessionInUrl: true`, `persistSession: true`, `autoRefreshToken: true`):
- The frontend is a Next.js app using `@supabase/supabase-js` for password sign-in and session handling; password recovery flows depend on Supabase Auth redirect configuration and the **production frontend origin**.
- After adopting **Vercel-generated `*.vercel.app`** as the canonical frontend origin (approved), you must configure Supabase Auth **Site URL** and **Redirect URLs** (exact names in Dashboard may vary) to include that origin for production, e.g.:
  - Site URL: `https://<your-app>.vercel.app` (or the exact canonical URL you designate)
  - Redirect allowlist entries should include the exact URLs your app uses for auth callbacks/recovery landing (e.g. `https://<your-app>.vercel.app/...` paths as implemented). **Do not use wildcards broadly** unless you fully understand the risk; prefer explicit URLs.
- If you test preview deployments, decide policy: either add specific preview origins temporarily (not recommended long-term) or restrict previews to a non-production Supabase project. This is an **owner decision** (**NEEDS CONFIGURATION**).
- **NOT VERIFIED** in this audit: no hosted Supabase Dashboard access; current/required redirect entries were not inspected. Any mismatch will break password recovery and/or OAuth/callback flows.

## 8. Database connection strategy and least-privilege requirements

### 8.1 Connection strategy (code/ops guidance)
- Django uses `dj_database_url.parse(DATABASE_URL, conn_max_age=0)` (`backend/config/settings.py`). Production requires `DATABASE_URL` when `DJANGO_DEBUG=false`; `TEST_DATABASE_URL` is only allowed in debug/local paths and must **not** be used on Render.
- **Strategy recommendation (from prior reports, reinforced):** use a **direct or pooler connection string appropriate for the chosen Supabase/Postgres deployment** as `DATABASE_URL`, supplied as a **Render secret**. Prefer settings that match your operational model (transaction/session pooler vs direct) per Supabase guidance for the project — **selection is a deployment decision** (**NEEDS CONFIGURATION**) and must be validated in practice (**NOT VERIFIED**).
- Do **not** expose `DATABASE_URL` to the frontend or commit it.

### 8.2 Least-privilege requirements
- The API **must** connect with a **database role subject to Row Level Security (RLS)** and with only the privileges required by the application. **Do not** use a **superuser** or a role with **BYPASSRLS** for the Django API in production.
- Repo evidence (migrations): `0005_rls.sql` revokes broad privileges from `anon`, `authenticated`, `PUBLIC` on domain tables and grants specific table/column privileges to `authenticated` (e.g. `donors/hospitals/requests` CRUD grants as written; `profiles` restricted with column-level update grant). RLS is enabled on domain tables with policies that rely on helper functions (e.g. `bdr_*` helpers) and JWT-derived claims set by the API middleware path (`request.jwt.claim.sub` etc., set transaction-locally by `SupabaseClaimsMiddleware`). `0009`/`0010` harden function search paths and revoke a dashboard helper from client roles.
- **Application-layer defense-in-depth:** Django verifies JWTs and enforces RBAC/ownership in code; RLS is an additional layer for direct PostgREST/client access patterns and defense-in-depth. Both matter.
- **Operational requirement:** provision/configure the Postgres role used in `DATABASE_URL` so that RLS applies as intended (not bypassed), and grants align with what the app needs. Hosted state (actual role, grants, whether migrations applied) is **NOT VERIFIED** here.

### 8.3 What is NOT needed
- This Django backend does **not** require a Supabase **service-role** key or secret API key for normal request handling (JWT verification uses JWKS or legacy HS256 secret only). Do not place service-role keys in backend env except never do so.

## 9. RLS policies review and production verification still required

### 9.1 Repo review (evidence-based)
- `supabase/migrations/0005_rls.sql` (summary from file review): revokes all on `donors,hospitals,profiles,requests` from `anon,authenticated,PUBLIC`; grants `SELECT/INSERT/UPDATE/DELETE` on `donors,hospitals,requests` to `authenticated`; for `profiles` grants `SELECT` and column-restricted `UPDATE (full_name)` to `authenticated`; enables RLS and defines policies for donors/hospitals/profiles/requests using helper functions (`bdr_is_admin`, `bdr_is_hospital`, `bdr_hospital_id`, `bdr_uid`) and ownership/admin rules as written in that migration. Profiles INSERT/DELETE not granted via policies in the shown pattern (managed by trusted processes/functions per comments).
- `0009_harden_function_search_paths.sql`: pins `search_path` for `bdr_uid()` and `set_updated_at()` (security hardening).
- `0010_revoke_rls_auto_enable.sql`: revokes `rls_auto_enable()` from `PUBLIC/anon/authenticated` if present (removes unintended RPC exposure).
- Prior reports (`D-01`, `D-02D`, `PRODUCTION_READINESS_REPORT`) state repository-level RLS migrations exist; hosted enforcement and migration application were **not verified** in those audits.

### 9.2 Production verification still required (NOT VERIFIED until performed)
The following must be confirmed in the **target hosted Supabase/Postgres** (approved process), not assumed from repo files:
1. **Migrations applied** in order through the intended migration set (including 0005, 0009, 0010 and any later migrations) to the production project.
2. **RLS enabled** on `public.donors`, `public.hospitals`, `public.profiles`, `public.requests` (and any related domain tables introduced later).
3. **Policies active** and behaving as intended for admin vs hospital vs unauthenticated/anon paths (especially request scoping and donor visibility rules aligned with app behavior).
4. **Grants/revokes** match migration intent (no accidental `PUBLIC`/`anon` write access; `authenticated` limited as designed).
5. **API database role**: connects as a role that is subject to RLS (no bypass) and has only required grants.
6. **Helper functions** (`bdr_uid`, role/hospital helpers, `assign_role`/related SECURITY DEFINER functions if used): present, search_path hardened where applicable, and execution/grant posture reviewed (do not weaken inadvertently).
7. **Live behavior tests** (controlled): verify hospital A cannot read hospital B requests/data per policy+app rules; admin can perform allowed actions; forged/invalid claims do not grant elevated access (aligned with “role from profiles, not JWT claims”).
8. **Seed/admin bootstrap**: confirm at least one admin profile exists and is correctly linked to a real Supabase Auth user for production operations (process-dependent).

## 10. Vercel Hobby plan suitability (assessment — decision support)

### 10.1 What this project appears to be (from repo)
- Next.js App Router frontend (TypeScript), static/server rendering patterns typical of a dashboard; API calls to a separate Django backend on Render. No evidence in reviewed files of heavy serverless function compute requirements beyond Next.js defaults, nor of known hard dependency on Vercel Pro-only features in the repo itself (no `vercel.json` requiring Pro features observed; `next.config.ts` minimal).

### 10.2 General considerations (plan constraints are subject to change; verify in Vercel)
Vercel Hobby (free tier) is commonly used for personal/non-commercial projects with limits around:
- **Commercial use restrictions** (Hobby is typically intended for personal/hobby use) — this is a **policy** point you must confirm against current Vercel terms for your organization/use case.
- **Bandwidth, build minutes, serverless function execution limits, and team/collaboration features** — may be constrained compared to Pro. If the registry is used by a real organization/clinic/hospital network in production, Hobby may be **inappropriate** due to usage limits or terms.
- **Preview deployments and team access** — Hobby is single-user oriented in practice; operational needs (multiple operators, environments) may push toward Pro/Team.
- **Custom domains**: not requested here (using `*.vercel.app`), which reduces one common constraint, but does not remove usage/terms limits.

### 10.3 Classification
- **NEEDS CONFIGURATION** (owner decision): confirm (a) whether this deployment is personal/hobby vs organizational/commercial under Vercel’s current terms, (b) expected traffic and build frequency against Hobby limits, and (c) whether you need team features, higher limits, or SLAs. Do **not** assume Hobby is appropriate for production hospital use without this confirmation.
- This audit **does not** access your Vercel account/plan; it cannot verify current limits for your account.

### 10.4 Practical recommendation (non-binding)
- For **evaluation/staging on a non-commercial basis** with low traffic, Hobby may be sufficient if terms allow — but still validate limits.
- For **any production use by an organization** (or if terms prohibit commercial use on Hobby), plan to use **Vercel Pro (or Team)** and budget accordingly; re-check after confirming actual usage patterns post-launch.

## 11. Prior audit cross-references (for continuity)
- `docs/D-01_DEPLOYMENT_READINESS_REPORT.md`: broad readiness matrix (backend/frontend/Supabase) with many items NEEDS CONFIGURATION/NOT VERIFIED/BLOCKED (e.g. DR-01 noted there).
- `docs/D-02A_RENDER_PREDEPLOYMENT_REPORT.md`: Render backend pre-deploy checks; recommends **NOT READY FOR RENDER SERVICE CREATION** until config verified (aligned with this audit’s domain/env focus).
- `docs/D-02D_RENDER_CONFIGURATION_REVIEW.md`: lists READY/NEEDS CONFIGURATION/BLOCKED/NOT VERIFIED for current D-02C state and production settings; concludes **NOT READY FOR CONFIGURATION** in that review context.
- `docs/D-02E_BLOCKER_ANALYSIS.md`: details BLOCKED/NEEDS CONFIGURATION/NOT VERIFIED items and safe resolution steps (domains/origins, Supabase decisions, post-service verification).

## 12. Prioritized checklist (decisions and actions before service creation)

Complete in order where dependencies exist. No secrets printed here; store secrets only in platform secret stores.

### P0 — Blockers / must-decide before safe configuration
1. **Approve exact production domains (no custom domains purchase assumed):** record the final canonical **Vercel `*.vercel.app`** frontend URL(s) to use in production (and preview policy). Record the final **Render `*.onrender.com`** API URL/hostname(s) once known/assigned context is fixed for this deployment. (Owner decision; required for CORS/hosts/frontend API base.)
2. **Decide `CSRF_TRUSTED_ORIGINS`:** set to `unset` at launch unless a concrete cookie/CSRF flow exists; if used, list exact HTTPS origins only. (Owner decision.)
3. **Confirm JWT strategy (prefer JWKS):** for the retained Supabase project, confirm whether tokens use asymmetric JWKS or legacy HS256. Document the choice and required backend env (`SUPABASE_URL`, optional overrides, or `SUPABASE_JWT_SECRET` only if HS256). Never use service-role keys.
4. **Confirm target Supabase project and Auth correctness:** project URL matches `SUPABASE_URL`; verify issuer/audience behavior for issued tokens (set overrides if non-default). (Dashboard checks.)
5. **Database connection plan:** choose the correct `DATABASE_URL` form for the intended Supabase/Postgres setup, use a **non-superuser, RLS-bound** role, ensure `TEST_DATABASE_URL` is never set on Render. (Ops decision; validate after setup.)

### P1 — Required Render/Vercel configuration (after P0 values known)
6. **Render service settings:** Root Directory `backend`, Build Command `pip install -r requirements.txt` (or equivalent), Start Command `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT`, Health Check Path `/health`, `PYTHON_VERSION=3.14.10`. Do not set `PORT` manually.
7. **Render env vars (production):** `DJANGO_DEBUG=false`, strong `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS` = exact Render API hostname(s) including probe host(s), `DATABASE_URL` (secret), `CORS_ALLOWED_ORIGINS` = exact Vercel HTTPS origin(s), `SUPABASE_URL` (+ JWKS/issuer/audience or HS256 secret as decided), `CSRF_TRUSTED_ORIGINS` only if decided, and ensure `TEST_DATABASE_URL` absent.
8. **Vercel env vars:** `NEXT_PUBLIC_SUPABASE_URL`, public key (`NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` and/or `NEXT_PUBLIC_SUPABASE_ANON_KEY` as used), `NEXT_PUBLIC_API_BASE_URL=https://<render-api>.onrender.com`, `NEXT_PUBLIC_ALLOW_DEV_LOGIN=false` (or unset). No secrets/service keys.

### P2 — Supabase Dashboard / hosted verification (before or immediately after controlled deploy)
9. **Auth redirects:** set Supabase Site URL and Redirect URL allowlist to the final canonical Vercel `*.vercel.app` origin(s) and required auth callback/recovery paths; define preview policy.
10. **Hosted DB/RLS verification (approved process):** confirm migrations applied (including RLS/grants/function hardening migrations), RLS enabled on domain tables, policies/grants match intent, API role is RLS-bound with least privilege, helper/function posture acceptable, and perform controlled live checks (hospital scoping, admin actions, invalid-token behavior).
11. **JWKS/live token sanity (controlled):** verify tokens from the target project verify against configured issuer/audience/JWKS path (no secrets logged).

### P3 — Deployment verification (after service/config exist)
12. Verify HTTPS on Render service; observe Linux build/start logs; confirm `/health` returns 200 with correct Host; validate CORS from approved frontend origin(s); run minimal authenticated API smoke tests; validate frontend login/recovery flows against final origins.
13. Confirm Vercel Hobby (or chosen plan) is appropriate for intended use (commercial/personal terms, limits, team needs) — **owner decision**.

### P4 — Ongoing operational hygiene
14. Keep `SECURE_PROXY_SSL_HEADER` and any Django SSL redirect disabled until proxy behavior is explicitly verified; do not re-enable debug or dev login in production.
15. Document rollback and post-deploy smoke checklist (aligned with prior reports) before broad rollout.

## 13. Constraints reaffirmed
- This document is a read-only audit. No Render/Vercel/Supabase resources were created or modified, no env files changed, no hosted DB accessed, no migrations run, no commits/pushes made.
- No secrets, tokens, UUIDs, database connection strings with credentials, emails, or phone numbers are included.