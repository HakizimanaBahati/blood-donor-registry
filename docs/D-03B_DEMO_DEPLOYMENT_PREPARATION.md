# D-03B — University Project Demo Deployment Preparation

Date: 2026-11-23  
Task type: read-only preparation (no hosting service creation, no code/env changes, no hosted DB/data access, no migrations, no commits/pushes)  
Context: **University project/demo only** (not a live operational hospital system). No custom domain purchase. Use platform-generated domains. Prefer **Vercel Hobby** and **Render Free** for the initial demonstration, subject to current plan eligibility and limits. Retain existing Supabase project and RLS; prefer **Supabase JWKS-based JWT verification**.

## 1. Review of D-03A and prior deployment reports (summary)

Reviewed (read-only): `docs/D-03A_PRODUCTION_CONFIGURATION_AUDIT.md`, `docs/D-02A_RENDER_PREDEPLOYMENT_REPORT.md`, `docs/D-02D_RENDER_CONFIGURATION_REVIEW.md`, `docs/D-02E_BLOCKER_ANALYSIS.md`, `docs/D-01_DEPLOYMENT_READINESS_REPORT.md`, `docs/PRODUCTION_READINESS_REPORT.md`, `docs/D-02G_RELEASE_CANDIDATE_REPORT.md`, `docs/D-02H_POST_COMMIT_VERIFICATION_REPORT.md` (and repo files referenced there: `backend/config/settings.py`, `backend/authentication/jwt.py`, `frontend/lib/supabase.ts`, migrations `0005/0009/0010`, etc.).

Key points carried forward:
- **Code/security posture (D-02C):** middleware order correct, explicit `CSRF_TRUSTED_ORIGINS` from env only, secure cookies/HSTS/headers posture as implemented, `CORS_ALLOW_CREDENTIALS=False`, auth unchanged. Post-commit verification (D-02H) reported `6829bb6` on `main`/`origin/main` with successful regression reruns recorded (120 backend tests OK in final run) and only untracked local files present.
- **Render backend readiness (D-02A/D-02D):** WSGI (`config.wsgi:application`) and `/health` correct; Gunicorn pinned in `requirements.txt`; **NOT READY** for service creation/configuration completion until approved env/service settings and verified domains/JWT strategy are applied and deployment verification performed.
- **D-03A conclusions:** approved planning assumptions are Render `*.onrender.com` API + Vercel `*.vercel.app` frontend, JWKS preferred, existing Supabase+RLS retained. Exact issuer/JWKS derived defaults from `SUPABASE_URL` (`…/auth/v1/.well-known/jwks.json`, issuer `…/auth/v1`, audience default `authenticated`) are implemented in code; live project correctness **not verified**. Many items remain **NEEDS CONFIGURATION** / **BLOCKED** (final domain values, Supabase redirect/JWT confirmation, hosted RLS/migration verification, Hobby/Free plan confirmation) and deployment verification **NOT VERIFIED**.
- **Demo intent:** this is a **university/demo** artifact, not a live hospital deployment; operational SLAs, compliance posture beyond basic technical controls, and high availability are out of scope for this preparation except noted risks.

## 2. Exact Render service configuration (demo, Render Free — subject to current plan)

**Classification (overall for “create/configure now”):** **NEEDS CONFIGURATION** (values and dashboard steps not performed here). Code/supporting files are **READY** for the intended shape.

### 2.1 Service settings (exact recommended values)
| Setting | Exact/value recommendation | Classification |
|---|---|---|
| Service type | Web Service (Python) | READY (pattern) |
| Environment | Python | READY |
| Repository/branch | Approved repo, branch `main` (or the demo branch you designate) at a known commit (current audited head `6829bb6` context). Confirm before creating service. | NEEDS CONFIGURATION |
| Root Directory | `backend` | READY (repo layout) |
| Build Command | `pip install -r requirements.txt` (or `python -m pip install -r requirements.txt`) | NEEDS CONFIGURATION (set in Render) |
| Start Command | `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT` | READY (command) / NEEDS CONFIGURATION (set in Render) |
| Health Check Path | `/health` | READY (endpoint exists) / NEEDS CONFIGURATION (set in Render) |
| Python runtime | `PYTHON_VERSION=3.14.10` (no repo pin file). Set explicitly. | NEEDS CONFIGURATION (env var on Render) |
| Region | Choose closest/acceptable region per Render Free availability (owner choice). | NEEDS CONFIGURATION |
| Instance/plan | **Render Free** for initial demo **if eligible and acceptable** (expect sleep/spindown behavior; see §8). | NEEDS CONFIGURATION (plan selection + eligibility) |
| Auto Deploy | Optional for demo; if enabled, understand it redeploys on pushes to the watched branch. | NEEDS CONFIGURATION (policy decision) |

### 2.2 Render environment variables (demo) — names only, placeholders in text
Set as Render env/secrets (no real values here). **Do not** set `TEST_DATABASE_URL`.

| Variable | Required? | Demo guidance (placeholders) | Classification |
|---|---|---|---|
| `DJANGO_DEBUG` | Required | `false` | NEEDS CONFIGURATION |
| `DJANGO_SECRET_KEY` | Required (**secret**) | `<strong-random-secret>` | NEEDS CONFIGURATION |
| `DJANGO_ALLOWED_HOSTS` | Required | Exact Render API hostname(s) from the created service, e.g. `<service-name>.onrender.com` (comma-separated if multiple). Must include host used by health probes. | NEEDS CONFIGURATION (unknown until service/domain known) |
| `DATABASE_URL` | Required (**secret**) | Postgres connection URL for the **existing Supabase project** (or the intended demo DB). Use a **non-superuser, RLS-bound** role for the API. | NEEDS CONFIGURATION (and must be validated operationally) |
| `CORS_ALLOWED_ORIGINS` | Required | Exact Vercel HTTPS origin(s), e.g. `https://<vercel-app>.vercel.app` (no wildcard, no trailing slash). | NEEDS CONFIGURATION (after Vercel URL known) |
| `SUPABASE_URL` | Required (for derived JWKS/issuer unless overridden) | `https://<project-ref>.supabase.co` | NEEDS CONFIGURATION |
| `SUPABASE_JWKS_URL` | Optional (prefer explicit only if needed) | If unset, derived as `<SUPABASE_URL>/auth/v1/.well-known/jwks.json` (JWKS preferred). | NEEDS CONFIGURATION/decision |
| `SUPABASE_JWT_ISSUER` | Optional | If unset, derived as `<SUPABASE_URL>/auth/v1`. Override only if project differs. | NEEDS CONFIGURATION/decision (verify in Supabase) |
| `SUPABASE_JWT_AUDIENCE` | Optional | Default `authenticated` unless overridden. | NEEDS CONFIGURATION/decision (verify in Supabase) |
| `SUPABASE_JWT_SECRET` | Optional (legacy HS256 only) | Leave unset for JWKS flow; if HS256 required by project, set only that secret (**never** service-role key). | NEEDS CONFIGURATION/decision |
| `CSRF_TRUSTED_ORIGINS` | Optional | Leave unset for demo unless a cookie/CSRF flow is introduced (Bearer-token API typically no). If set, exact HTTPS origins only. | NEEDS CONFIGURATION (decision) |
| `PYTHON_VERSION` | Required (recommended) | `3.14.10` | NEEDS CONFIGURATION |
| `PORT` | Provided by platform | Do not set. | READY (automatic) |

### 2.3 Notes specific to Render Free (demo)
- Free web services may **spin down after inactivity** and have **cold starts**; the first request after idle can be slow (affects live demos). Plan a short warm-up before presenting. (**NOT VERIFIED** until tested on your account/region.)
- Build/deploy minutes and runtime limits are subject to Render’s current Free tier terms; verify eligibility/limits in the Render dashboard/account. (**NEEDS CONFIGURATION/NOT VERIFIED**.)

## 3. Exact Vercel project configuration (demo, Vercel Hobby — subject to current plan)

**Classification:** **NEEDS CONFIGURATION** (no project created/configured here). Repo/frontend shape is **READY** (`frontend/` Next.js app, `next.config.ts` minimal).

### 3.1 Project settings (exact recommended values)
| Setting | Exact/value recommendation | Classification |
|---|---|---|
| Import source | Approved Git repository and branch (`main` or demo branch), after intended changes committed (D-02H shows only untracked files locally; ensure demo deployment uses the correct committed tree). | NEEDS CONFIGURATION |
| Root Directory | `frontend` | READY |
| Framework Preset | Next.js | READY |
| Node.js Version | Set explicitly to a supported LTS available in Vercel (repo has no pin file). Prefer **24.x** if available per prior guidance; satisfy Next.js minimum (`>=20.9.0`) as stated in repo deps context. Confirm in Vercel UI. | NEEDS CONFIGURATION |
| Install Command | `npm ci` | READY (lockfile present) |
| Build Command | `npm run build` | READY |
| Output Directory | Leave framework default | READY |
| Environment scope (Production) | Set all required Production env vars below. | NEEDS CONFIGURATION |
| Plan | **Vercel Hobby** for initial demo **if eligible** and terms allow (non-commercial/personal as typically defined). Organizational/commercial use may require paid plan — see §8. | NEEDS CONFIGURATION (owner decision + account verification) |

### 3.2 Vercel environment variables (Production, demo)
Set in Vercel (Production). **Only public values** — never secrets.

| Variable | Required? | Demo guidance (placeholders) | Classification |
|---|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Required | `https://<project-ref>.supabase.co` (public) | NEEDS CONFIGURATION |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` or `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Required (use one consistently) | `<public-publishable-or-anon-key>` (public only) | NEEDS CONFIGURATION |
| `NEXT_PUBLIC_API_BASE_URL` | Required | `https://<render-service>.onrender.com` (exact, no trailing slash). Must equal Render API origin allowed by backend CORS. | NEEDS CONFIGURATION (after Render URL known) |
| `NEXT_PUBLIC_ALLOW_DEV_LOGIN` | Required | `false` (or unset). Demo should not enable dev-login UI in production-style deploy unless you explicitly accept backend debug=false behavior (dev-login API is blocked when `DJANGO_DEBUG=false`). | NEEDS CONFIGURATION |

### 3.3 Preview deployments (demo note)
- Vercel previews get different URLs; adding them to backend `CORS_ALLOWED_ORIGINS`/Supabase redirects is error-prone for a quick demo. **Recommended:** demo using the **Production** Vercel URL only, or explicitly add a single tested preview URL temporarily (**owner decision**). (**NEEDS CONFIGURATION/NOT VERIFIED**.)

## 4. Complete environment-variable checklist (public vs secrets)

### 4.1 Public (safe to expose to browser / non-secret config)
| Name | Where | Notes |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Vercel | Supabase project URL (public). |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` / `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Vercel | Public/publishable key only. |
| `NEXT_PUBLIC_API_BASE_URL` | Vercel | HTTPS Render API origin, no trailing slash. |
| `NEXT_PUBLIC_ALLOW_DEV_LOGIN` | Vercel | Set `false` for demo deploy. |
| `DJANGO_ALLOWED_HOSTS` | Render | Hostnames only (no scheme, no secrets). |
| `CORS_ALLOWED_ORIGINS` | Render | Exact HTTPS origins (no secrets). |
| `CSRF_TRUSTED_ORIGINS` | Render (optional) | Exact HTTPS origins if used. |
| `SUPABASE_URL` | Render | Project URL (not a secret by itself, but treat carefully; do not confuse with service keys). |
| `SUPABASE_JWKS_URL` | Render (optional) | URL if explicitly set. |
| `SUPABASE_JWT_ISSUER` | Render (optional) | Issuer string if overridden. |
| `SUPABASE_JWT_AUDIENCE` | Render (optional) | Audience string if overridden. |
| `PYTHON_VERSION` | Render | `3.14.10`. |

### 4.2 Secrets (must be stored only in platform secret stores)
| Name | Where | Notes |
|---|---|---|
| `DJANGO_SECRET_KEY` | Render | Strong random value; required when `DJANGO_DEBUG=false`. |
| `DATABASE_URL` | Render | Postgres connection string (credentials). Use RLS-bound API role. |
| `SUPABASE_JWT_SECRET` | Render (only if HS256) | Legacy HS256 secret only; **never** Supabase service/secret API keys. Prefer leaving unset with JWKS. |

### 4.3 Explicitly forbidden in frontend/Vercel or repo
- Supabase `sb_secret_...` / service-role keys, any database passwords in git, JWT signing secrets in `NEXT_PUBLIC_*`, `TEST_DATABASE_URL` on Render. (**Classification: READY as a rule in code/docs; operational enforcement NEEDS CONFIGURATION.**)

## 5. Required CORS and ALLOWED_HOSTS values once generated domains are known

### 5.1 When you know the domains (fill these in)
- **Render API (generated):** after creating the Web Service, note the hostname, e.g. `<service-name>.onrender.com`.
  - `DJANGO_ALLOWED_HOSTS=<service-name>.onrender.com` (add any additional exact API hostnames only if used; comma-separated, no scheme). Must include the hostname Render uses for health probes.
- **Vercel frontend (generated):** note the canonical Production URL, e.g. `https://<project>.vercel.app` (or the exact assigned domain shown in Vercel).
  - `CORS_ALLOWED_ORIGINS=https://<project>.vercel.app` (exact HTTPS, no trailing slash). Add other exact origins only if intentionally allowed (risky for demos).
- **Frontend API base:** `NEXT_PUBLIC_API_BASE_URL=https://<service-name>.onrender.com` (must match backend CORS origin intent: browser calls this origin).

### 5.2 CSRF
- `CSRF_TRUSTED_ORIGINS`: **leave unset** for this demo unless you introduce cookie/CSRF flows. If set later, use exact HTTPS origins matching the frontend.

### 5.3 Classification
- Pattern/template: **READY**. Actual values: **NEEDS CONFIGURATION** until Render/Vercel services are created and URLs observed. Live correctness (probe host, real CORS behavior): **NOT VERIFIED**.

## 6. Supabase Auth redirect URL configuration (demo)

**Classification:** **NEEDS CONFIGURATION** in Supabase Dashboard; **NOT VERIFIED** by this audit (no hosted access).

For a demo using Vercel `*.vercel.app` (Production canonical URL `https://<vercel-app>.vercel.app`):
1. In Supabase Auth settings, set **Site URL** to the canonical demo frontend origin (exact), e.g. `https://<vercel-app>.vercel.app` (confirm the exact field name in your Dashboard).
2. Add **Redirect URLs** (allowlist) for any auth flows the app uses (password recovery, email confirmation redirects if applicable). Include exact URLs used by the frontend, e.g. `https://<vercel-app>.vercel.app/reset-password` (or the actual paths in the app) and any callback paths the code relies on. Prefer explicit URLs over wildcards.
3. If you demo from a **Vercel preview URL**, you must either add that specific preview origin to the allowlist temporarily (not recommended) or avoid preview-based demos for auth flows. Decide and document this choice.
4. Ensure `SUPABASE_URL` in Render matches the same project; confirm issuer/audience expectations align (defaults `…/auth/v1`, `authenticated`) or set overrides explicitly.
5. **Do not** place any secret keys in frontend env; only public URL + publishable/anon public key.

Operational note: password recovery and “magic link” style redirects will fail silently or redirect incorrectly if allowlists do not include the demo origin (**demo availability risk**).

## 7. Database connection and least-privilege requirements (from code/migrations; no hosted access)

### 7.1 Code/migration evidence (read-only)
- Backend: `DATABASE_URL` required when `DJANGO_DEBUG=false` (`backend/config/settings.py`); parsed via `dj_database_url`; `conn_max_age=0`. `TEST_DATABASE_URL` only allowed in debug/local fallback paths — must be absent on Render.
- Auth/RLS integration in app: `SupabaseClaimsMiddleware` sets transaction-local Postgres config (`request.jwt.claim.sub`, `request.jwt.claim.role='authenticated'`) and sets local role `authenticated` when a verified token is present; Django still resolves app role/profile from the database (`authentication.services.get_app_user`) — **role is not trusted from JWT claims alone** for app authorization.
- Migrations (repo): `supabase/migrations/0005_rls.sql` revokes broad grants from `anon/authenticated/PUBLIC` on domain tables, grants specific privileges to `authenticated` (including column-restricted updates on `profiles`), enables RLS with policies using helpers (`bdr_*`), and comments note profiles inserts/deletes managed by trusted processes. `0009_harden_function_search_paths.sql` hardens `bdr_uid()` and `set_updated_at()` search_path. `0010_revoke_rls_auto_enable.sql` revokes `rls_auto_enable()` from client roles if present.

### 7.2 Requirements (demo must follow these)
- Use the **existing Supabase PostgreSQL project** (approved). Set `DATABASE_URL` in Render to that project’s connection string for the API (secret).
- The connected role **must be subject to RLS** and have **least privilege**: no superuser, no `BYPASSRLS` for the API role. Grants should align with migration intent (app uses `authenticated` role context in DB session per middleware). (**NEEDS CONFIGURATION** operationally; not verified against hosted DB here.)
- Do **not** use Supabase service-role key in the backend for normal API operation (JWT verified via JWKS/legacy HS256 secret only).
- Hosted verification still required (not done): migrations applied in order through the intended set (including 0005/0009/0010), RLS enabled on domain tables, policies/grants effective, helper functions present/hardened as intended, and controlled tests for role scoping (admin vs hospital) and invalid tokens. (**NOT VERIFIED**.)

### 7.3 Classification
- Repo evidence of RLS/grants design and app behavior: **READY** (documented). Correct production/hosted configuration and enforcement: **NEEDS CONFIGURATION / NOT VERIFIED**.

## 8. Free-tier limitations and demo availability risks (Render Free + Vercel Hobby)

**Classification:** **NEEDS CONFIGURATION** to confirm current terms/limits in your accounts; risks below are **informational (NOT VERIFIED** against your exact plan state at demo time except general known patterns).

### 8.1 Render Free (backend API)
- **Spin down / cold starts:** free web services may sleep after periods of inactivity; first request can be slow (tens of seconds in worst cases) causing demo hiccups or timeouts. Mitigation: open the API health URL shortly before demo, or be prepared to wait.
- **Resource limits:** CPU/memory and runtime constraints may affect performance under load (demo should use light traffic).
- **Build/deploy limits:** monthly build minutes or deploy frequency limits may apply per current Render terms.
- **Network/region availability:** service region affects latency; choose appropriately.
- **No SLA:** unsuitable for “always-on” expectations; demo may be unavailable during maintenance windows or if limits exceeded.
- **HTTPS:** provided for `*.onrender.com` (platform-managed) — still verify after deploy (**NOT VERIFIED**).

### 8.2 Vercel Hobby (frontend)
- **Terms/policy:** Hobby is typically for personal/non-commercial use; confirm this university demo is allowed under current Vercel terms (organizational/commercial use may violate terms or require paid plan). (**NEEDS CONFIGURATION** owner decision.)
- **Usage limits:** bandwidth, build minutes, serverless function invocations/execution limits may apply; a small demo is usually fine but traffic spikes or frequent rebuilds can hit limits.
- **Preview deployments:** limited collaboration features on Hobby; preview URLs may complicate CORS/redirect allowlists.
- **No guaranteed SLA:** similar to Render Free for production expectations (not the goal here, but relevant if demo is time-sensitive).

### 8.3 Supabase (existing project)
- Plan limits (database size, bandwidth, auth MAU, API requests) depend on your current Supabase plan; demo usage is typically small but **verify** you are within limits and that the project is not paused. (**NOT VERIFIED**.)
- Auth redirect configuration mistakes cause login/recovery failures (see §6).
- JWT verification depends on network reachability from Render to Supabase JWKS endpoints (usually fine, but **NOT VERIFIED** in practice until tested).

### 8.4 Combined demo risks (practical)
- **First impression latency:** cold start on Render + frontend load can feel slow; warm up before presenting.
- **Env misconfiguration:** wrong `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, or Supabase redirect URLs will break health checks, API calls, or login — treat as **top demo blockers**.
- **Data/state:** demo uses the existing Supabase project/DB; changes are real to that project unless you use a separate demo project (not stated). Be careful with test data.
- **Security posture is demo-appropriate only in intent:** do not present as production-hardened beyond what code provides; keep `DJANGO_DEBUG=false`, dev login off, secrets out of repo/frontend.

## 9. Safe deployment sequence with rollback checkpoints

**Principle:** do steps in order, verify after each checkpoint. Do **not** expose the demo publicly until checkpoints pass. This is preparation guidance (no actions executed here).

### Checkpoint A — Pre-flight (local/repo, no hosted changes)
1. Confirm branch/commit to deploy (recommend `6829bb6` or the latest commit that includes approved D-02C changes you intend). Verify `git status` expectations for release (D-02H context: only untracked local files remain). (**READY** if using audited head; **NEEDS CONFIGURATION** if choosing another commit.)
2. Confirm no secrets in repo (`.env` files not committed patterns per `.gitignore`; only examples). (**READY** by policy; verify before push/deploy.)
3. Have ready (written down, stored securely): planned Render service name idea, planned Vercel project/canonical URL, Supabase project URL, JWT strategy decision (JWKS preferred), and a plan for `DATABASE_URL`/`DJANGO_SECRET_KEY` values (entered only into platform dashboards). (**NEEDS CONFIGURATION**.)

**Rollback/checkpoint A:** if repo is dirty in unexpected ways, stop and clean/commit intentionally (separately authorized).

### Checkpoint B — Supabase (Dashboard, manual) — before or in parallel with hosting
4. Verify Supabase project URL and JWT settings (issuer/audience, JWKS vs HS256) match intended backend env. Prefer JWKS (no `SUPABASE_JWT_SECRET`). (**NEEDS CONFIGURATION/NOT VERIFIED**.)
5. Configure Auth Site URL and Redirect URLs to the planned Vercel Production origin(s) (use placeholders until Vercel URL known, then update). (**NEEDS CONFIGURATION/NOT VERIFIED**.)
6. Confirm the API will use an RLS-bound, least-privilege DB role for `DATABASE_URL` (operational plan). Do not use service-role key for backend API. (**NEEDS CONFIGURATION/NOT VERIFIED**.)

**Rollback/checkpoint B:** if Supabase settings are uncertain, do not proceed to public demo; fix redirects/JWT settings first.

### Checkpoint C — Create/configure Render (backend) first
7. Create Render Web Service (Free if chosen) from the approved repo/branch with settings from §2.1 (Root `backend`, Build/Start, Health `/health`, `PYTHON_VERSION=3.14.10`).
8. Set Render env vars from §2.2 (all required). Ensure `DJANGO_DEBUG=false`, secrets set, `TEST_DATABASE_URL` absent.
9. Deploy and watch build logs. If build fails, fix via new commit (separately authorized) or correct settings; do **not** guess secrets.
10. After first deploy, note the assigned `*.onrender.com` hostname.

**Rollback/checkpoint C:** if deploy fails repeatedly, pause. Keep service private/unlisted in practice by not sharing URL yet; fix config and redeploy. If you must abort, delete the Render service to stop costs/usage exposure (optional for demo).

### Checkpoint D — Verify backend health (before frontend)
11. Test `GET https://<render-host>/health` from a browser or HTTP client. Expect HTTP 200 and `{"status":"ok"}` (per `HealthView`). If 400/5xx, check `DJANGO_ALLOWED_HOSTS` includes the exact host, build/start logs, and env vars.
12. (Optional but recommended) Perform a minimal authenticated API smoke test using a known Supabase test user only if you have one prepared (do not create accounts in production-like steps here except planned). (**NOT VERIFIED** until executed.)

**Rollback/checkpoint D:** if `/health` fails due to host/CORS/env, correct Render env and redeploy. Do not proceed to frontend integration until basics are sane.

### Checkpoint E — Create/configure Vercel (frontend)
13. Create/import Vercel project (Hobby if chosen) with Root `frontend`, Node version per §3.1, `npm ci`, `npm run build`.
14. Set Production env vars from §3.2 using the confirmed Render URL and Supabase public values. Set `NEXT_PUBLIC_ALLOW_DEV_LOGIN=false`.
15. Deploy and note the canonical `*.vercel.app` URL.

**Rollback/checkpoint E:** if build fails, fix code/config via authorized commits or correct env vars; redeploy. If wrong API URL set, update env and redeploy.

### Checkpoint F — Align CORS, hosts, Supabase redirects (cross-cutting)
16. Update Render `CORS_ALLOWED_ORIGINS` to the exact Vercel Production URL (and any explicitly approved extra origins). Redeploy/restart as needed.
17. Confirm Render `DJANGO_ALLOWED_HOSTS` includes the Render hostname (and probe host). Redeploy if changed.
18. Update Supabase Auth Site URL and Redirect URLs to the Vercel Production URL and required paths. (**Manual step.**)
19. Optionally warm Render (hit `/health`) before demo to reduce cold start.

**Rollback/checkpoint F:** revert to previous known-good env values in dashboards if a change breaks the demo, then retest.

### Checkpoint G — Demo-readiness smoke tests (before showing publicly)
20. Open frontend URL: app loads without blank-screen build errors.
21. Attempt sign-in with a prepared demo/test account (non-production data awareness). Verify dashboard loads for the expected role.
22. Verify API calls succeed (no CORS errors in browser console for allowed origin). Verify unauthorized requests behave as expected (401/403 envelopes per app behavior).
23. (If time permits) Quick check: create/view a request or donor flow consistent with demo script, noting any slow cold-start delays.

**Rollback/checkpoint G:** if critical flow fails, use the last known-good configuration (revert env/dashboard changes) and document the issue; do not improvise secret changes in logs.

### Checkpoint H — After demo
24. If the demo must not remain public, consider disabling the Vercel deployment or the Render service, or removing shared URLs (demo-only hygiene). Do **not** rotate secrets casually without a plan, but note any exposed non-secret URLs are public by design (`*.vercel.app`/`*.onrender.com`).

## 10. Checks that must pass before the first public demo

All items below should be satisfied (or explicitly accepted as risks) before sharing the demo URL publicly:

1. **Branch/commit known:** deploying from an approved commit (e.g. `6829bb6` context) with no unintended tracked changes planned for deploy.
2. **Render service settings:** Root `backend`, correct Build/Start, Health Path `/health`, `PYTHON_VERSION` set.
3. **Render env (production):** `DJANGO_DEBUG=false`, `DJANGO_SECRET_KEY` set (secret), `DJANGO_ALLOWED_HOSTS` includes Render hostname(s), `DATABASE_URL` set (secret, RLS-bound role intent), `CORS_ALLOWED_ORIGINS` set to exact Vercel URL, `SUPABASE_URL` set, JWT strategy decided (JWKS preferred; `SUPABASE_JWT_SECRET` only if HS256), `TEST_DATABASE_URL` absent, `CSRF_TRUSTED_ORIGINS` unset unless required.
4. **Backend health:** `GET /health` returns HTTP 200 with expected body from the public Render URL.
5. **Vercel settings:** Root `frontend`, correct install/build, Node version set appropriately, Production env vars set (public Supabase URL + public key, `NEXT_PUBLIC_API_BASE_URL` pointing to Render URL, `NEXT_PUBLIC_ALLOW_DEV_LOGIN=false`).
6. **Frontend loads:** Vercel Production URL opens the app without build/runtime crashes in normal navigation.
7. **CORS:** browser requests from the Vercel origin to the Render API succeed (no CORS errors blocking core flows).
8. **Supabase Auth config:** Site URL and Redirect URLs include the Vercel Production origin and required paths; test sign-in works for a prepared account.
9. **AuthZ sanity (smoke):** at least one admin and/or one hospital flow works as expected for demo accounts (role scoping not obviously broken). Invalid/expired behavior is acceptable if it shows proper errors (not stack traces).
10. **No secrets exposed:** no service-role keys, JWT secrets, or `DATABASE_URL` in frontend env, browser output, or committed files; demo narration avoids revealing secrets.
11. **Demo risk acknowledgment:** you have warned/demo-noted possible cold starts (Render Free) and any plan-limit concerns (Hobby/Free). (**Owner acknowledgment.**)
12. **Hosted data awareness:** demo uses the existing Supabase project; you understand any data created/modified is real to that project (unless you used a separate demo project).

**If any of 1–10 fail:** do **not** present as a working public demo; fix via the sequence in §9 or revert changes.

## 11. Remaining blockers (explicit)

1. **Final generated domains unknown until services exist:** Render `*.onrender.com` hostname and Vercel `*.vercel.app` canonical URL not yet assigned in this repo context — blocks final `DJANGO_ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `NEXT_PUBLIC_API_BASE_URL`, and Supabase redirect allowlist values. (**BLOCKED** until services created/URLs observed, then **NEEDS CONFIGURATION**.)
2. **Supabase Dashboard decisions/verification not performed here:** JWT strategy confirmation (JWKS vs HS256), issuer/audience correctness for issued tokens, Auth Site URL/Redirect URLs, and hosted migration/RLS/grant/role verification for the existing project. (**BLOCKED/NOT VERIFIED** until performed in Dashboard/approved process.)
3. **Database role/connection operational validation:** `DATABASE_URL` must use a non-superuser, RLS-bound role with correct grants; this is not verified against the hosted DB in this audit. (**NEEDS CONFIGURATION/NOT VERIFIED**.)
4. **Plan eligibility/limits confirmation:** Vercel Hobby and Render Free eligibility, current terms, and limits for this account/context not verified here (including Hobby commercial-use policy relevance for a university/demo presentation context as applicable). (**NEEDS CONFIGURATION/NOT VERIFIED**.)
5. **Prior release-gate caveats (from earlier reports):** some D-01A-era gates and broader deployment verifications were previously reported open/not verified in full; for a **demo** this may be acceptable if acknowledged, but it remains a **BLOCKED/NOT VERIFIED** risk area for “production-ready” claims. (**NOT VERIFIED** for full production; demo use requires explicit risk acceptance.)
6. **Deployment verification not performed:** no live build/deploy, no live `/health` confirmation, no live CORS/JWT end-to-end test from the generated domains performed in this audit. (**NOT VERIFIED**.)

## 12. Exact step-by-step deployment checklist (copy/paste friendly)

Use this as the runbook order (mark each done; stop if any fails):

- [ ] **A1.** Choose deploy commit (e.g. `6829bb6`) and confirm no unintended tracked changes for release; keep untracked local files untouched.
- [ ] **A2.** Confirm secrets will only be entered into Render/Vercel/Supabase dashboards (no secrets in git).
- [ ] **B1.** In Supabase (existing project): confirm JWT strategy (prefer JWKS), `SUPABASE_URL` matches project, note issuer/audience defaults (`…/auth/v1`, `authenticated`) or plan overrides.
- [ ] **B2.** In Supabase: plan Auth Site URL + Redirect URLs for the future Vercel Production URL; decide preview policy (recommend Production-only for demo).
- [ ] **B3.** Plan `DATABASE_URL` using a non-superuser, RLS-bound role (do not use service-role key for backend).
- [ ] **C1.** Create Render Web Service (Free if eligible): Root `backend`, Build `pip install -r requirements.txt`, Start `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT`, Health `/health`, set `PYTHON_VERSION=3.14.10`.
- [ ] **C2.** Set Render env vars: `DJANGO_DEBUG=false`, `DJANGO_SECRET_KEY` (secret), `DJANGO_ALLOWED_HOSTS` (placeholder then set to real host), `DATABASE_URL` (secret), `CORS_ALLOWED_ORIGINS` (set after Vercel URL), `SUPABASE_URL`, optional JWT overrides/JWKS only if needed, **no** `SUPABASE_JWT_SECRET` if JWKS, `CSRF_TRUSTED_ORIGINS` unset, `PYTHON_VERSION=3.14.10`.
- [ ] **C3.** Deploy Render; record assigned hostname `<render-host>.onrender.com`; set `DJANGO_ALLOWED_HOSTS=<render-host>.onrender.com` (and redeploy if changed).
- [ ] **D1.** Verify `https://<render-host>/health` returns HTTP 200 JSON `{"status":"ok"}`.
- [ ] **E1.** Create/import Vercel project (Hobby if eligible): Root `frontend`, Node version set, Install `npm ci`, Build `npm run build`.
- [ ] **E2.** Set Vercel Production env: `NEXT_PUBLIC_SUPABASE_URL`, public key (`NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` or `NEXT_PUBLIC_SUPABASE_ANON_KEY`), `NEXT_PUBLIC_API_BASE_URL=https://<render-host>.onrender.com`, `NEXT_PUBLIC_ALLOW_DEV_LOGIN=false`. Deploy; record `<vercel-app>.vercel.app`.
- [ ] **F1.** Set Render `CORS_ALLOWED_ORIGINS=https://<vercel-app>.vercel.app` (exact); redeploy/restart if required.
- [ ] **F2.** Set Supabase Site URL + Redirect URLs to `https://<vercel-app>.vercel.app` (and required paths); save.
- [ ] **F3.** (Optional) Warm Render by calling `/health` before demo.
- [ ] **G1.** Open Vercel URL; confirm app loads.
- [ ] **G2.** Sign in with prepared demo account; confirm role-appropriate dashboard loads.
- [ ] **G3.** Confirm no CORS errors for core API calls; confirm auth errors are handled cleanly (no secret leakage).
- [ ] **H1.** Before public sharing, complete §10 checks 1–12 (or explicitly accept listed risks for demo).
- [ ] **H2.** After demo, consider disabling/unpublishing services if no longer needed (demo hygiene).

## 13. Constraints reaffirmed

- This document is **read-only preparation**. No hosting services were created, no code/env files changed, no hosted Supabase data accessed/modified, no migrations run, no commits/pushed.
- No secrets, tokens, UUIDs, database URLs with credentials, emails, or phone numbers are included. Use platform secret stores only.