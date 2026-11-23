# D-03E — Final Hosted Readiness Report (University Demo / Pre-Production Assessment)

Date: 2026-11-23  
Task type: read-only synthesis (no service creation, no env/file/code/migration changes, no hosted DB/data access, no migrations, no commits/pushes)  
Scope: Consolidate D-01, D-02A–D-02H, D-03A–D-03D into a single final hosted readiness assessment for the Blood Donor Registry (Django REST backend + Next.js frontend + Supabase Postgres/Auth + RLS migrations in repo). This is a **university project/demo context** (not a live hospital operations system), unless explicitly stated otherwise.

> **Safety / constraints (reaffirmed):** No secrets, tokens, passwords, UUIDs, database URLs, or access keys are printed in this report. No hosted services were created or modified; no migrations executed; no hosted Supabase/Render/Vercel data accessed. Existing untracked files were not altered by this task.

---

## 1) Current overall readiness status

### Overall assessment: **READY WITH CONDITIONS**

**Plain language:** The repository is in a **reviewable, commit-pinned state** for demo-oriented hosting prep (`main == origin/main == 6829bb6`, with only untracked local files preserved), and the codebase documents and implements key security/correctness patterns (middleware order, explicit env-driven CORS/hosts/CSRF handling, JWT verification with JWKS preference, transaction-local JWT GUCs + `SET LOCAL ROLE authenticated` on verified requests, RLS + defense-in-depth app authz defined in migrations). However, **no live hosted deployment has been verified**, and several **operationally critical items are not yet confirmed** (exact generated domains wired end-to-end, Supabase Auth/JWT + migration/RLS/grants + API DB role state, Render/Vercel plan eligibility/limits, and end-to-end HTTPS/CORS/JWT/role-scoping smoke tests). A university demo is **feasible if** the “Before deploying” and “Before public demo” checklists below are completed by authorized operators; **production/hospital use remains out of scope** until those verifications and any resolved gate items from prior reports are satisfied.

**Status labels used throughout:** `READY`, `NEEDS CONFIGURATION`, `BLOCKED`, `NOT VERIFIED` (plus explicit **RESOLVED** notes where prior blockers were closed in-repo by approved commits).

---

## 2) Final classification table

Legend (final): **READY** = repo/config pattern supports it and evidence exists in repo/docs; **NEEDS CONFIGURATION** = required values/decisions/settings must be applied; **BLOCKED** = cannot be completed now due to missing external approval/access or unresolved dependency; **NOT VERIFIED** = not checked live/hosted; **RESOLVED** = was a blocker, now fixed/closed by documented work (still may require hosted verification).

| Area | Classification | Notes (evidence / constraints) |
|---|---|---|
| Repo git state (audited line) | **RESOLVED** (audit context) / **READY** (current snapshot context) | D-02G/D-02H: commit `6829bb6` (`chore(security): apply D-02C Django hardening settings and tests`) pushed to `origin/main`; `main == origin/main == 6829bb6`, no tracked changes. D-02H created `docs/D-02H_POST_COMMIT_VERIFICATION_REPORT.md` concluding **VERIFIED — POST-COMMIT REGRESSION PASSED** with a noted transient full-suite DB create conflict followed by successful rerun (120/120). Untracked preserved (incl. reports + `backend/b05b7_r.py`). |
| D-01A release gate / prior critical code findings | **NOT VERIFIED (for hosted go-live) / partially resolved in code lineage** | D-01A listed critical items (e.g. profile approval blocker, legacy auth imports, DB role handling concerns in that era). D-01B reported fixes applied/committed in earlier steps (e.g. `6bb8c73` blood-request notes length fix). Current code shows JWT-based auth (`SupabaseJWTAuthentication`, middleware sets GUCs + `SET LOCAL ROLE authenticated` for verified tokens) and profile resolution from verified `sub`. **Hosted operational confirmation still required.** |
| Backend runtime shape (Render) | **READY** (repo) | `backend/config/wsgi.py` → `config.wsgi:application`; `backend/config/urls.py` exposes `/health` (`config.health.health_view`); Gunicorn pinned in `backend/requirements.txt`; `README.md`/D-02A document Start `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT`, Root `backend`, Health `/health`. |
| Django security/hardening settings (committed) | **READY** (repo, `6829bb6`) | `backend/config/settings.py`: `DEBUG` env-driven (prod requires `DEBUG=false`), `SECRET_KEY` required when debug false, `ALLOWED_HOSTS` from env, CORS explicit/origins-only (`CORS_ALLOW_CREDENTIALS=False`), CSRF trusted origins explicit env-only (no CORS derivation, no hardcoded platform domains), secure cookies/HSTS/headers posture as coded, `SECURE_SSL_REDIRECT=False`, proxy header unset pending verification, DB from `DATABASE_URL` (debug fallback to `TEST_DATABASE_URL` only), middleware order includes `CorsMiddleware` then `SecurityMiddleware` then `SupabaseClaimsMiddleware`, tests present (`backend/config/tests/test_settings.py`). D-02C documented; D-02H verified post-commit. |
| JWT / Supabase Auth verification (code) | **READY** (code behavior) | `backend/authentication/jwt.py`: JWKS via `SUPABASE_JWKS_URL` (derived from `SUPABASE_URL` + `/auth/v1/.well-known/jwks.json` when unset), issuer derived from `SUPABASE_URL` + `/auth/v1` when unset, audience default `authenticated`, algorithms include HS256/RS256/ES256, rejects bad alg/none, requires claims, verifies sig/exp/aud/iss; HS256 requires secret (no prod fallback). Middleware uses verified token to set `request.jwt.claim.sub`, `request.jwt.claim.role='authenticated'`, `SET LOCAL ROLE authenticated` inside `transaction.atomic()`. DRF auth resolves app user from `profiles` by verified `sub`. (D-03A/D-03D.) |
| Supabase project/JWT/redirects (hosted) | **NOT VERIFIED** / **NEEDS CONFIGURATION** | D-03A/D-03C: expected formats documented (URL, JWKS, issuer, audience). Manual Dashboard checks required (project identity, signing strategy/JWKS vs HS256, `iss`/`aud`, providers, Site URL + Redirect URLs for Vercel demo origin/paths, migration state, RLS/grants, DB role posture). **BLOCKED** from live confirmation by lack of hosted inspection in this task. |
| Supabase migrations / RLS / DB functions (repo) | **READY** (repo) | Migrations 0001–0010 present and reviewed (roles/tables/indexes/functions, RLS/grants 0005, donor link/fixes 0006–0008, search_path hardening 0009, revoke `rls_auto_enable` 0010). App intent: defense-in-depth RLS + app authorization; middleware sets RLS context for verified requests. **NOT VERIFIED** on hosted DB (applied state, drift, role bypass). (D-03C/D-03D.) |
| Database connection security (code vs hosted) | **NEEDS CONFIGURATION** / **NOT VERIFIED** (hosted) | Code: `DATABASE_URL` only (prod), `conn_max_age=0`, middleware wraps requests in `transaction.atomic()` and sets claim GUCs + `SET LOCAL ROLE authenticated` when verified (transaction-local). App authz from `profiles` by verified `sub`. Risks: hosted role must be non-superuser, no `BYPASSRLS`, able to `SET ROLE authenticated`, least privilege; external pooler behavior unknown. D-03D concludes **NOT VERIFIED for safe use as-is** on hosted stack until checked. |
| Frontend (Vercel) shape | **READY** (repo) | `frontend/` Next.js app; `frontend/lib/supabase.ts` uses env `NEXT_PUBLIC_SUPABASE_URL` + publishable/anon key(s); `README.md`/D-03B list required `NEXT_PUBLIC_*` vars. Production must set `NEXT_PUBLIC_ALLOW_DEV_LOGIN=false` (or unset). |
| Render/Vercel demo config (exact steps/values guidance) | **NEEDS CONFIGURATION** | D-03B provides exact recommended settings (Root `backend`, build `pip install -r requirements.txt`, start Gunicorn with `$PORT`, health `/health`, `PYTHON_VERSION=3.14.10`, Vercel Root `frontend`, `npm ci`/`npm run build`). No services created; final hostnames/origins unknown until provisioned. |
| Free-tier / plan constraints (Render Free, Vercel Hobby) | **NEEDS CONFIGURATION** / **NOT VERIFIED** | D-03B/D-03A state: prefer Render Free + Vercel Hobby for demo **if eligible and acceptable**; cold starts/sleep, build/runtime limits, Vercel Hobby terms (non-commercial/personal typical constraints) must be confirmed by account owner. **NOT VERIFIED** here. |
| End-to-end hosted verification (smoke: health, CORS, auth, RLS scoping) | **NOT VERIFIED** | No live Render/Vercel/Supabase calls performed in these audits. Required after deployment: `/health`, JWT auth, CORS from Vercel origin, hospital/admin scoping, no secret leakage, HTTPS behavior notes. |
| Domain/cert/HTTPS operational details | **NOT VERIFIED** (platform-managed) | Render/Vercel provide HTTPS for generated domains; Django does not force SSL redirect/trust proxy headers in current code (intentional pending verification). Operational confirmation after deploy still needed. |
| Production/hospital-grade readiness (beyond demo) | **BLOCKED** (contextual) | D-01A/D-02E/D-02G historically flagged release blockers/gates in earlier states; D-02G concluded NOT READY FOR RELEASE COMMIT at that time (context), D-02C applied hardened settings later, D-02H post-commit regression passed. Even so, **live hosted verification, Supabase/role/RLS confirmation, and any outstanding owner decisions** mean **broader “production ready” is not claimed** here; this report is a **demo/pre-production readiness assessment**. |

---

## 3) “Ready now” vs “still required before deploying” vs “recommended before public demo”

### 3.1 Ready now (repo/state evidence)
- **Git/audit baseline:** `6829bb6` on `main`/`origin/main`, no tracked changes; untracked local helper/reports preserved as documented. (D-02H)
- **Backend deploy shape in repo:** WSGI + `/health` + pinned Gunicorn + documented commands/roots. (D-02A, code)
- **Security settings applied in code:** env-driven secrets/hosts/CORS/CSRF, secure cookie/HSTS/header posture, JWT config derived from `SUPABASE_URL`, middleware order correct, auth flow via verified JWT + profile lookup. (D-02C, settings/middleware/jwt)
- **RLS/DB design documented in migrations:** 0001–0010 reviewed with intent (RLS, grants, helpers, hardening, revocations). (D-03C/D-03D)
- **Documentation set exists** for audits/plans/checklists (D-01* through D-03D + this D-03E target) to guide operators.

### 3.2 Still required before deploying (minimum, actionable)
Complete these **before** creating/configuring Render/Vercel production-like demo services (or before first real deploy), with **no secrets printed** into docs/logs you share:
1. **Confirm demo targets and ownership:** university/demo scope acknowledged; decide whether to **reuse existing Supabase project** (recommended if suitable) after manual checks (D-03C P1–P5). If reuse is not viable, plan a separate demo project (separate operational task).
2. **Supabase Dashboard (manual, no changes recorded here):** verify project URL matches `SUPABASE_URL`, JWT strategy (prefer JWKS; confirm `iss`/`aud` vs defaults or set overrides), Auth providers as needed, **Site URL + Redirect URLs** for the planned Vercel demo origin/paths, and review migration/RLS/grants/role posture conceptually against repo (D-03C §8). **Do not** run migrations/SQL from this report.
3. **Render (Web Service, Free if eligible):** create/configure with Root `backend`, build `pip install -r requirements.txt`, start `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT`, health `/health`, set `PYTHON_VERSION=3.14.10`. Set env vars: `DJANGO_DEBUG=false`, `DJANGO_SECRET_KEY` (secret), `DJANGO_ALLOWED_HOSTS` = exact `<service>.onrender.com` (and any host probes use), `DATABASE_URL` (secret, RLS-bound non-bypass role), `CORS_ALLOWED_ORIGINS` = exact Vercel HTTPS origin(s), `SUPABASE_URL` (+ overrides only if needed), `SUPABASE_JWT_SECRET` only if HS256 required (otherwise unset). **Do not** set `TEST_DATABASE_URL`.
4. **Vercel (Hobby if eligible):** import repo, Root `frontend`, Node per Vercel guidance (Next.js requires compatible version), `npm ci` / `npm run build`. Set Production env: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` or `NEXT_PUBLIC_SUPABASE_ANON_KEY` (public only), `NEXT_PUBLIC_API_BASE_URL=https://<service>.onrender.com`, `NEXT_PUBLIC_ALLOW_DEV_LOGIN=false`.
5. **Wire final origins:** after domains exist, set Render `DJANGO_ALLOWED_HOSTS` and `CORS_ALLOWED_ORIGINS` to the exact generated values; set Vercel `NEXT_PUBLIC_API_BASE_URL` to that Render origin; update Supabase Auth redirects to the exact Vercel origin/paths.
6. **Database role/pooling safety (operational):** ensure `DATABASE_URL` role is **not** superuser, **no `BYPASSRLS`**, and can support app pattern (`SET ROLE authenticated` in transaction context as used); understand Supabase pooler mode implications (D-03D). Validate with smoke tests after deploy.
7. **Post-deploy verification (minimum):** `GET /health` returns 200; browser login via Vercel → API calls succeed with valid JWT; invalid token rejected; CORS allows only approved origin; basic role scoping (hospital vs admin) behaves as expected; no secrets in client bundles/network beyond public Supabase config.

### 3.3 Recommended before public/demo presentation (beyond minimum deploy)
- Run a **short warm-up** against Render Free (cold starts) before demos; have a fallback plan if service sleeps. (D-03B)
- Limit Supabase Auth Redirect URLs to **exact** production Vercel origin(s); avoid broad wildcards; be cautious with preview URLs. (D-03A/D-03B)
- Record a **demo runbook** (who has admin/hospital test accounts provisioned via approved `assign_role` flow, what data is test/demo-only). (D-03C)
- Optionally enable tighter observability/log review during demo window (without exposing secrets) and revert if noisy; note `authentication` log level behavior (settings set to WARNING in non-debug). (settings)
- If you plan to show Supabase Dashboard or tokens, use sanitized screens (no secrets/URLs with embedded creds copied into notes).

---

## 4) Exact next actions checklist

1. **(Owner) Approve demo scope and project reuse:** confirm university/demo only, confirm whether to reuse existing Supabase project (D-03C recommendation: reuse **conditional** pending P1–P5).
2. **(Operator, Supabase Dashboard — manual):** complete D-03C prioritized checks P1–P7: project URL, JWT strategy + `iss`/`aud`, migration state 0001–0010 (incl. 0005/0008/0009/0010), RLS/grants posture, DB role (non-superuser, no `BYPASSRLS`, `SET ROLE authenticated` capable), Site URL/Redirect URLs set for planned Vercel origin, demo accounts/bootstrap (`assign_role`), then post-deploy smoke readiness.
3. **(Operator, Render):** create Web Service (Free if eligible) from approved repo/branch (`main` at `6829bb6` context or newer approved commit), Root `backend`, build `pip install -r requirements.txt`, start `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT`, health `/health`, `PYTHON_VERSION=3.14.10`. Set env vars per §3.2 above (secrets in Render only). Do not set `TEST_DATABASE_URL`.
4. **(Operator, Vercel):** create/import project (Hobby if eligible), Root `frontend`, set Node compatible with Next.js, `npm ci`/`npm run build`. Set Production `NEXT_PUBLIC_SUPABASE_URL`, public key var(s), `NEXT_PUBLIC_API_BASE_URL` (initially placeholder allowed only until Render URL known), `NEXT_PUBLIC_ALLOW_DEV_LOGIN=false`.
5. **(Operator, wire values):** after Render URL issued, set `DJANGO_ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` on Render; set `NEXT_PUBLIC_API_BASE_URL` on Vercel; redeploy both if needed; set Supabase Redirect URLs to final Vercel origin(s)/paths.
6. **(Operator, verification):** run checks: `GET https://<render>/health` → 200; Vercel sign-in works; API rejects missing/invalid Bearer token; CORS allows only approved Vercel origin; hospital user cannot access another hospital’s requests; admin flows work as intended; inspect browser/network for accidental secret exposure (should be none). Document results privately (no secrets in shared notes).
7. **(Owner, go/no-go for broader use):** if demo is successful and you consider extending beyond demo, complete D-03A P0–P4 and D-03D required operational checks; treat any unresolved items as **BLOCKED/NOT VERIFIED** for production claims.

---

## 5) Final recommendation: **Demo-ready only with conditions** (with explicit staging-first guidance)

### Recommendation (clear)
- **Demo-ready only with conditions:** The project is in a **good repo/documented state for a university demo**, but it is **not verified as hosted/demo-safe end-to-end** until the conditions in §3.2 and §4 are satisfied (Supabase JWT/redirects/migrations/RLS/role checks, correct Render/Vercel env wiring, plan eligibility confirmed, and successful smoke tests).
- **Not recommended as “production-ready” now:** Do **not** present this as production/hospital-ready without completing hosted verification, resolving any outstanding owner-approved gates from prior D-01A/D-02E lineage as applicable, and confirming RLS/role/pooling behavior in the deployed topology.
- **Staging-first guidance (strongly recommended):** even for a demo, perform a **staging-style dry run** in order: (a) validate Supabase config and migrations/RLS state in the chosen project, (b) deploy backend to Render and verify `/health` + JWT rejection behavior with a test token path, (c) deploy frontend to Vercel pointed at that backend and verify CORS + sign-in, (d) run role-scoping smoke tests. Only then run the live demo. If you skip staging steps, expect common failures (wrong `iss`/`aud`, redirect mismatch, CORS origin typo, DB role/RLS issues, Render cold starts).

**Final bottom line:** **Proceed to deploy for a university demo only after the listed conditions are met; otherwise treat as NOT VERIFIED/BLOCKED for a reliable demo.**

---

## Appendix A — Key files referenced (for traceability)
- Backend: `backend/config/settings.py`, `backend/config/urls.py`, `backend/config/health.py`, `backend/authentication/middleware.py`, `backend/authentication/jwt.py`, `backend/authentication/authentication.py`, `backend/authentication/services.py`, `backend/config/tests/test_settings.py`, `backend/requirements.txt`
- Frontend: `frontend/lib/supabase.ts`, `frontend/.env.example`, `frontend/next.config.ts`, `README.md`
- Supabase migrations (repo): `supabase/migrations/0001_roles.sql` … `0010_revoke_rls_auto_enable.sql`
- Prior reports: `docs/D-01_DEPLOYMENT_READINESS_REPORT.md`, `docs/D-01A_RELEASE_GATE_REPORT.md`, `docs/D-01B_DEFECT_FIX_REPORT.md`, `docs/D-02A_RENDER_PREDEPLOYMENT_REPORT.md`–`D-02H_POST_COMMIT_VERIFICATION_REPORT.md`, `docs/D-03A_PRODUCTION_CONFIGURATION_AUDIT.md`, `docs/D-03B_DEMO_DEPLOYMENT_PREPARATION.md`, `docs/D-03C_SUPABASE_DEMO_PREFLIGHT.md`, `docs/D-03D_DATABASE_CONNECTION_SECURITY_AUDIT.md`, `docs/PRODUCTION_READINESS_REPORT.md`