# D-03C — Supabase Demo Environment Preflight

Date: 2026-11-23  
Task type: read-only inspection (no hosted access, no data changes, no migrations/SQL executed, no Dashboard changes, no code/env changes, no git commits/pushes)  
Context: University project/demo (not a live hospital system). Reuse the **existing** Supabase project if configuration is suitable. Prefer **asymmetric JWT verification via JWKS**. Preserve all existing RLS protections.

## 1. Reviewed sources (read-only)

- `docs/D-03A_PRODUCTION_CONFIGURATION_AUDIT.md`
- `docs/D-03B_DEMO_DEPLOYMENT_PREPARATION.md`
- Backend: `backend/config/settings.py`, `backend/authentication/jwt.py`, `backend/authentication/authentication.py`, `backend/authentication/middleware.py`, `backend/authentication/permissions.py`, `backend/authentication/services.py`, `backend/config/test_runner.py` (context only)
- Supabase migrations (all files): `supabase/migrations/0001_roles.sql`, `0002_tables.sql`, `0003_indexes.sql`, `0004_functions.sql`, `0005_rls.sql`, `0006_request_donor_link.sql`, `0007_fix_donors_phone_regex.sql`, `0008_fix_donors_phone_regex_literal_plus.sql`, `0009_harden_function_search_paths.sql`, `0010_revoke_rls_auto_enable.sql`

No secrets, tokens, UUIDs, database URLs, or credentials are printed in this document.

## 2. Exact expected Supabase URL, JWKS URL, issuer, and audience formats (from code)

### 2.1 Backend environment inputs (`backend/config/settings.py`)
- `SUPABASE_URL` (env): trimmed; trailing slash stripped. Empty if unset.
- `SUPABASE_JWKS_URL` (env): if empty and `SUPABASE_URL` is set, derived as:  
  **`{SUPABASE_URL}/auth/v1/.well-known/jwks.json`**
- `SUPABASE_JWT_ISSUER` (env): if empty and `SUPABASE_URL` is set, derived as:  
  **`{SUPABASE_URL}/auth/v1`**
- `SUPABASE_JWT_AUDIENCE` (env): defaults to **`authenticated`** if unset/blank after strip.
- `SUPABASE_JWT_SECRET` (env): used only for **legacy HS256** verification. In non-debug production (`DJANGO_DEBUG=false`) there is **no** development fallback; if you rely on HS256 you must set this secret explicitly. **Do not** use Supabase service/secret API keys.
- Allowed algorithms: `("HS256","RS256","ES256")` (`JWT_ALGORITHMS`).

### 2.2 Verification behavior (`backend/authentication/jwt.py`)
- Reads unverified JWT header to inspect `alg` and `kid` (diagnostic only; logs sanitized). Rejects missing/invalid structure, disallows `alg="none"`, requires claims `exp`, `sub`, `iat`. Verifies signature, expiry, audience, issuer (when configured).
- **JWKS (asymmetric) path:** when `alg` is RS256/ES256 (per allowed set), uses `PyJWKClient` against `settings.SUPABASE_JWKS_URL` (cached) to obtain the signing key from the token (`get_signing_key_from_jwt`). If JWKS is not configured/reachable in a recoverable way, verification fails with a generic “temporarily unavailable” style error to clients (details sanitized in logs).
- **HS256 path:** requires `SUPABASE_JWT_SECRET`; decodes with that secret.
- On success: `VerifiedToken(subject=<uuid>, claims=...)`; `sub` must be a valid UUID string.
- Middleware sets Postgres transaction-local settings from the verified token (`request.jwt.claim.sub`, `request.jwt.claim.role='authenticated'`) and sets local role `authenticated` for the request transaction when a verified token is present; DRF authentication prefers `request.verified_token` when set or verifies again. **Application authorization/role comes from `public.profiles` lookup by `sub` (via `authentication.services.get_app_user`), not from trusting arbitrary JWT role claims** for app roles.

### 2.3 Exact string formats to expect (operational)
- **Project URL:** `https://<project-ref>.supabase.co` (no trailing slash in practice; code strips trailing slash on `SUPABASE_URL`).
- **JWKS URL:** `https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json`
- **Issuer:** `https://<project-ref>.supabase.co/auth/v1`
- **Audience:** typically `authenticated` (confirm against tokens issued by the target project; override via `SUPABASE_JWT_AUDIENCE` only if different).
- **`sub`:** UUID of the Supabase Auth user (must validate as UUID in code).

**Classification:** **READY** (code-defined formats); **NOT VERIFIED** (whether the existing project emits these exact `iss`/`aud`/key strategy for your demo environment until checked in Dashboard/against real tokens).

## 3. Supabase Dashboard settings that must be manually checked (no changes made here)

Perform these in the **existing** Supabase project (Dashboard). Do **not** paste secrets into docs or chat.

1. **Project URL** matches the backend `SUPABASE_URL` exactly (scheme/host). Confirm this is the intended demo project.
2. **JWT signing / keys (prefer JWKS):** determine whether Auth issues **asymmetric (RS256/ES256)** tokens with JWKS or **legacy HS256**. If JWKS: confirm the JWKS endpoint is published and reachable from the internet (Render will fetch it). Align Render env: prefer **no** `SUPABASE_JWT_SECRET`, set `SUPABASE_URL` (or explicit `SUPABASE_JWKS_URL` if needed). If HS256 is unavoidable, set `SUPABASE_JWT_SECRET` only (never service/secret API keys).
3. **JWT claims:** verify `iss` and `aud` in issued access tokens. If different from defaults (`…/auth/v1`, `authenticated`), set `SUPABASE_JWT_ISSUER` / `SUPABASE_JWT_AUDIENCE` on Render explicitly.
4. **Auth providers:** confirm email/password (and any providers you demo) are enabled as intended; user lifecycle matches demo needs.
5. **Auth URL configuration:** **Site URL** and **Redirect URLs** allowlist must include the final Vercel demo origin and any exact callback/recovery paths the frontend uses (see §7). Wrong values break login/recovery flows.
6. **Database project identity:** confirm this is the intended project (demo data only as stated). **Do not** inspect/export sensitive data here beyond operational confirmation.
7. **API roles / connection model (operational):** confirm the database role used by `DATABASE_URL` in Render is **not** superuser and is **RLS-bound** (cannot bypass RLS) with least privilege (see §6). This is typically verified via SQL/role settings conceptually; **do not** run SQL from this audit — note as manual check.
8. **Migrations state (hosted):** confirm which migrations have been applied in this project (expected order/list below). **Do not** run migrations from this audit.
9. **Key exposure hygiene:** only public/publishable keys in Vercel/frontend (`NEXT_PUBLIC_SUPABASE_URL` + publishable/anon public key). Never `sb_secret_...`, service-role keys, JWT secrets, or `DATABASE_URL` in frontend or repo.

**Classification:** **NEEDS CONFIGURATION** for any values not yet set; **NOT VERIFIED** until you complete Dashboard checks.

## 4. Migration ordering and expected migration state (repository)

### 4.1 Ordered file list (from repo)
1. `0001_roles.sql` — creates/ensures roles `anon`, `authenticated`, `service_role` (idempotent-ish guards), grants schema usage, sets default privileges in `public` for `authenticated`/`service_role` (tables/sequences) in that context.
2. `0002_tables.sql` — creates domain tables: `public.hospitals`, `public.donors`, `public.profiles` (FK to `auth.users`), `public.requests`; constraints including blood types, units, status, notes length (`<=1000`), profile role/hospital consistency, donor phone/checks as written.
3. `0003_indexes.sql` — indexes for search/sorting/pagination and unique normalized phone index on donors.
4. `0004_functions.sql` — creates `auth` schema if missing; defines `public.bdr_uid()`, `bdr_is_admin()`, `bdr_is_hospital()`, `bdr_hospital_id()` (SECURITY DEFINER helpers), revokes/grants on helpers, defines `set_updated_at()` trigger function, attaches triggers to `donors`/`requests`, defines `public.assign_role(...)` (SECURITY DEFINER) restricted to `service_role` execution.
5. `0005_rls.sql` — revokes broad privileges from `anon/authenticated/PUBLIC` on domain tables; grants specific privileges to `authenticated` (table/column restrictions noted below); enables RLS and creates policies for `donors`, `hospitals`, `profiles`, `requests` using `bdr_*` helpers and ownership/admin rules.
6. `0006_request_donor_link.sql` — adds optional `requests.donor_id` FK to `donors` (ON DELETE SET NULL) and index.
7. `0007_fix_donors_phone_regex.sql` — drops/replaces `donors_phone_format` constraint (corrective regex form noted in file).
8. `0008_fix_donors_phone_regex_literal_plus.sql` — further corrective replacement of `donors_phone_format` using POSIX class form `[+]` (current intended form per file comment).
9. `0009_harden_function_search_paths.sql` — redefines `bdr_uid()` and `set_updated_at()` with `search_path = public, pg_temp` (idempotent re-declare).
10. `0010_revoke_rls_auto_enable.sql` — revokes `public.rls_auto_enable()` from `PUBLIC/anon/authenticated` if that function exists (idempotent guard).

### 4.2 Expected migration state (for “reuse existing project” judgment)
- **Expected:** migrations **0001 through 0010 applied in order** on the existing Supabase project (at minimum through 0010 for the current repo state described by these files). In particular: tables/indexes/functions present, **RLS enabled and policies/grants from 0005 in effect**, phone constraint in the **0008** form, function hardening **0009** applied, and `rls_auto_enable` revoked if present **0010** applied.
- **Demo note:** the project is stated to contain only test/demo data — this is acceptable for a university demo **if** data is non-sensitive and you understand it may be shared/visible per your demo setup. It is **not** the same as a production data posture decision.

**Classification:** **READY** (ordering/documented intent from repo). **NOT VERIFIED** (actual applied state on the hosted project). **BLOCKED** for confident reuse only if hosted state is unknown or diverges in ways that break auth/RLS/app behavior (must be verified manually).

## 5. RLS policies, grants, helper functions, and database-role requirements (from source)

### 5.1 Roles/schema bootstrap (0001)
- Ensures `anon`, `authenticated`, `service_role` roles exist (defensive for non-Supabase Postgres). Grants `USAGE` on `public` to these roles. Sets default privileges for future objects created by `postgres` to grant `SELECT/INSERT/UPDATE/DELETE` on tables and `USAGE/SELECT` on sequences to `authenticated` and `service_role` (context for ownership/migrations). **Note:** explicit per-table grants/revokes in later migrations are authoritative for current behavior shown there.

### 5.2 Domain tables (0002, 0006)
- Core tables: `hospitals`, `donors`, `profiles`, `requests`. `profiles.id` references `auth.users(id)` ON DELETE CASCADE. `requests` includes `requester_profile_id`, `donor_id` added in 0006 (FK to donors, SET NULL). Constraints enforce enums, positive units (<=10000), notes length <=1000, role/hospital consistency on profiles.

### 5.3 Helper functions (0004, 0009)
- `public.bdr_uid()`: returns UUID from `request.jwt.claim.sub` or parsed from `request.jwt.claims` JSON (`sub`), STABLE. **0009** sets `search_path = public, pg_temp`.
- `public.bdr_is_admin()`: SECURITY DEFINER, looks up `profiles` by `bdr_uid()` where role is `admin`. **0004** sets `search_path = public`; **0009 does not re-touch it** in the provided files (so its search_path remains as set in 0004 unless changed elsewhere). Execution revoked from `PUBLIC/anon`, granted to `authenticated`, `service_role`.
- `public.bdr_is_hospital()`: SECURITY DEFINER, checks hospital role for `bdr_uid()`. Same EXECUTE grants/revokes as admin helper; search_path set in 0004.
- `public.bdr_hospital_id()`: SECURITY DEFINER, returns `hospital_id` for current hospital-profile user. Same EXECUTE posture; search_path set in 0004.
- `public.set_updated_at()`: trigger function; **0009** sets `search_path = public, pg_temp` and is used by triggers on `donors`, `requests`.
- `public.assign_role(uuid, varchar, varchar, uuid default null)`: SECURITY DEFINER, validates role/admin/hospital rules, requires matching `auth.users` row, upserts `profiles`. **EXECUTE revoked from PUBLIC/anon/authenticated; granted to `service_role` only** (per 0004). This is the intended privileged path to assign roles (not callable by normal authenticated API clients via that grant).

### 5.4 RLS and grants (0005) — key points
- `REVOKE ALL ON public.donors, public.hospitals, public.profiles, public.requests FROM anon, authenticated, PUBLIC;`
- `GRANT SELECT, INSERT, UPDATE, DELETE ON ... donors, hospitals, requests TO authenticated;`
- `profiles`: `REVOKE ALL ... FROM authenticated; GRANT SELECT ...; GRANT UPDATE (full_name) ...` (column-level restriction intended to prevent role/hospital_id escalation via PostgREST).
- **donors:** RLS enabled. SELECT allowed if `bdr_is_admin()` OR `bdr_is_hospital()` (authenticated). INSERT/UPDATE/DELETE restricted to admin (with matching WITH CHECK on UPDATE).
- **hospitals:** RLS enabled. SELECT allowed if admin OR `id = bdr_hospital_id()` (so hospital users see only their own hospital row context as written). Mutations restricted to admin.
- **profiles:** RLS enabled. SELECT if `id = bdr_uid() OR bdr_is_admin()`. UPDATE allowed only when updating own row (`id = bdr_uid()`) and WITH CHECK same; no INSERT/DELETE policies shown (profile creation handled by `assign_role`/trusted processes per comment).
- **requests:** RLS enabled. SELECT/INSERT/UPDATE/DELETE allowed if admin OR `hospital_id = bdr_hospital_id()` (hospital scoped). Comments indicate Django also enforces rules in app code (defense in depth).
- **rls_auto_enable (0010):** if function exists, `REVOKE ALL ... FROM PUBLIC, anon, authenticated` (reduces accidental exposure via RPC).

### 5.5 Database-role requirements for the Django API (operational)
- The API connects using `DATABASE_URL` (server-side). For security, this role should be a **PostgreSQL role that is subject to RLS** (not a superuser, **not** `BYPASSRLS`) and should have only the privileges needed. Because the app sets `SET LOCAL ROLE authenticated` in a transaction when a verified JWT is present (per `SupabaseClaimsMiddleware`), the effective RLS context in that request path is intended to align with `authenticated` policies **plus** the transaction-local JWT claim GUCs set by the app. 
- Practically: the login/connection role must be permitted to `SET ROLE authenticated` (or an equivalent mechanism used in your deployment) in that context, and the `authenticated` privileges/grants defined by migrations (especially 0005) are the baseline the app relies on for PostgREST-style expectations; Django uses ORM/SQL through that connection. **This is a critical operational check**: misconfigured roles (e.g. using a bypassing role) can silently weaken RLS. (**NOT VERIFIED** on hosted DB.)
- The backend does **not** require Supabase `service_role` key for normal request handling; `assign_role` is granted to `service_role` in migrations (privileged admin provisioning path), not used by the Django API JWT flow described here.

**Classification (repo):** **READY** (migrations define RLS/grants/helpers as above). **NOT VERIFIED** (hosted role is RLS-bound, grants applied as written, `auth.users`/helper dependencies intact, no conflicting manual changes). 

## 6. Minimum safe database permissions required by the Django backend (inferred from code + migrations)

This is an inference from repository evidence (not a hosted audit). “Minimum safe” means least privilege consistent with observed behavior.

### 6.1 What the backend does (relevant to DB)
- Uses a direct Postgres connection (`DATABASE_URL`) via Django/psycopg. AuthN: verifies Supabase JWT (JWKS or HS256) in Django, resolves local app user/profile from `public.profiles` by `sub` (`authentication.services.get_app_user`). Middleware sets `request.jwt.claim.sub`, `request.jwt.claim.role='authenticated'`, and runs request DB work inside a transaction that does `SET LOCAL ROLE authenticated` when a verified token exists (so RLS policies written for role `authenticated` and helper functions reading JWT GUCs behave consistently with the app’s model).
- Domain operations are performed by Django ORM/querysets against `public.donors`, `public.hospitals`, `public.profiles`, `public.requests` (and related app logic). Migrations show `authenticated` is granted `SELECT, INSERT, UPDATE, DELETE` on `donors, hospitals, requests` and `SELECT` plus `UPDATE (full_name)` on `profiles` (0005). Application code enforces business rules (roles, hospital scoping, eligibility) in addition to RLS.

### 6.2 Minimum safe expectations (practical)
- **Connection role (the role in `DATABASE_URL`)**: must be able to connect to the intended database and must be able to **assume/effect the `authenticated` RLS context** as implemented (app does `SET LOCAL ROLE authenticated` in-transaction when token verified). In practice this means the login role must have **`SET ROLE authenticated`** (or equivalent privileges) in that deployment model; **must not** be a superuser and **must not** have `BYPASSRLS`. This is the most important hosted check.
- **Effective privileges under RLS (`authenticated`)**: should be no more than what migrations grant (0005): table DML on the four domain tables as specified, with `profiles` updates limited to `full_name` at the grant level and further restricted by RLS/policies. The app should not require broad owner/superuser rights.
- **Functions used by RLS/app expectations:** the `bdr_*` helper functions and `set_updated_at()` trigger function must exist and be executable in the contexts relied upon (0004 grants `EXECUTE` on helpers to `authenticated` and `service_role`; triggers run as defined). `assign_role` is for privileged provisioning (`service_role` grant) — not required by the running Django API request path for normal operations.
- **Extensions/schemas:** `auth` schema referenced conceptually (profiles FK to `auth.users`, helpers may read JWT settings); standard Supabase setup provides `auth.users` and JWT claim mechanisms. No extra app-owned extensions are introduced by the listed migrations beyond normal Postgres features used.

**Classification:** **NEEDS CONFIGURATION** (must be verified/configured on hosted DB/role). **NOT VERIFIED** (actual hosted role attributes, whether `SET ROLE authenticated` is permitted as used, and that no extra broad privileges exist).

## 7. Supabase Auth Site URL and redirect URL requirements (demo)

From `docs/D-03A`/`D-03B` and frontend behavior (`frontend/lib/supabase.ts` uses Supabase Auth client with `persistSession`, `autoRefreshToken`, `detectSessionInUrl: true`):
- **Site URL:** set to the canonical Vercel demo Production origin, e.g. `https://<vercel-app>.vercel.app` (exact value once known).
- **Redirect URLs (allowlist):** add every exact URL the app uses for auth callbacks and password recovery landing flows (paths must match the frontend implementation). Use explicit URLs; avoid broad wildcards for demo safety.
- **Preview URLs:** Vercel previews use different origins; adding them is error-prone. Recommended for demo: use Production URL only, or add a single tested preview URL temporarily if absolutely necessary (**owner decision**).
- **Mismatch effects:** login/session detection or password recovery redirects can fail or send users to blocked URLs.
- **Backend alignment:** `SUPABASE_URL` on Render must point to the same Supabase project as the frontend uses.

**Classification:** **NEEDS CONFIGURATION** (must be set in Dashboard). **NOT VERIFIED** (current values not inspected).

## 8. Sanitized checklist for manually verifying the live project (no secrets)

Complete in the Supabase Dashboard and via controlled app tests (do **not** paste secrets/URLs with embedded credentials into shared logs unnecessarily). Replace angle-bracket placeholders mentally with your real non-secret values only where helpful; do **not** record secrets here.

### A. Project & URL
- [ ] Confirm the correct Supabase project is the one used by demo (name/ref matches intended).
- [ ] `Project URL` equals the value you will set as `SUPABASE_URL` on Render (same host).

### B. Auth / JWT
- [ ] Determine signing method: **JWKS (asymmetric)** preferred. If HS256 is used, document that `SUPABASE_JWT_SECRET` must be set on Render (secret) — and confirm it is **not** a service key.
- [ ] If JWKS: confirm JWKS endpoint is reachable conceptually from public internet (or note Render egress); after deploy, validate a real login token verifies (via app behavior).
- [ ] Inspect an issued access token (in a secure local session tool) for `iss` and `aud`: expect `iss` like `https://<project-ref>.supabase.co/auth/v1`, `aud` like `authenticated` unless overridden. If different, plan `SUPABASE_JWT_ISSUER` / `SUPABASE_JWT_AUDIENCE` overrides on Render.
- [ ] Confirm email/password (and other needed providers) enabled as intended.

### C. Auth redirects
- [ ] Site URL set to canonical Vercel demo origin (e.g. `https://<vercel-app>.vercel.app`).
- [ ] Redirect URLs allowlist includes all required auth callback/recovery paths used by the frontend (exact). No unnecessary broad wildcards.
- [ ] Decision recorded for preview URLs (disabled for demo vs explicitly listed).

### D. Migrations (expected state)
- [ ] Verify migrations applied through **0001–0010** in order (names as in repo). Pay special attention to: **0005** (RLS/grants), **0008** (current donor phone constraint form per repo), **0009** (function search_path hardening), **0010** (`rls_auto_enable` revoked if present).
- [ ] Spot-check: `public.profiles` exists with expected columns/constraints intent; triggers on `donors`/`requests` for `updated_at` present; `assign_role` exists and is not executable by `anon/authenticated`/`PUBLIC` in practice (per 0004 intent).

### E. RLS & grants (conceptual + spot checks)
- [ ] RLS enabled on `donors`, `hospitals`, `profiles`, `requests`.
- [ ] Policies exist consistent with 0005 (admin vs hospital scoping for requests/hospitals/donors as designed; profiles self-read/admin-read and self-update of `full_name` only).
- [ ] No unintended broad grants to `anon`/`PUBLIC` on domain tables (per 0005 intent). `authenticated` has the limited grants described.
- [ ] `rls_auto_enable` revoked from client roles if the function exists (0010 intent).

### F. Database role used by `DATABASE_URL` (Render)
- [ ] The connection role is **not** a superuser and **does not** have `BYPASSRLS`.
- [ ] The role can support the app’s pattern of setting local role/claims in-transaction as implemented (operationally confirmed by successful authenticated API calls in demo tests) — **do not** weaken RLS to “make it work”.
- [ ] Role has only necessary privileges aligned with migrations/app needs (least privilege).

### G. Demo data & safety
- [ ] Confirm data in project is test/demo-only as stated; understand it may be visible to anyone with demo access you grant.
- [ ] At least one admin-capable profile/user path exists for demo (via `assign_role`/trusted process) so you can test admin flows — **managed outside this repo audit**.

### H. Post-deploy app smoke (after Render/Vercel configured)
- [ ] From Vercel demo URL, sign in succeeds; invalid token rejected by API.
- [ ] Hospital-scoped user cannot see another hospital’s requests (behavioral check).
- [ ] Admin can access admin-only flows permitted by app.
- [ ] No secrets appear in browser devtools/network payloads beyond normal public Supabase client config.

**Classification for this checklist:** **NEEDS CONFIGURATION/NOT VERIFIED** until completed manually.

## 9. Blockers to reusing the existing Supabase project

Potential blockers (any one can prevent safe/demo-successful reuse until resolved):

1. **Unknown/incorrect JWT configuration:** project issues tokens with `iss`/`aud`/algorithm different from backend expectations and no overrides planned; or JWKS unreachable from Render. (**BLOCKER risk** until verified.)
2. **Auth redirect mismatch:** Site URL/Redirect URLs not aligned to the Vercel demo origin/paths → broken login or recovery. (**BLOCKER for auth flows** until fixed.)
3. **Migration drift or incomplete migration state:** hosted DB missing 0001–0010 or diverged (especially RLS 0005, phone constraints 0007/0008, hardening 0009, 0010). Could cause runtime errors or security gaps. (**BLOCKER** until reconciled by approved process.)
4. **DB role misconfiguration:** `DATABASE_URL` uses a superuser/BYPASSRLS role, or lacks ability to operate under the app’s RLS/role model → security failure or broken behavior. (**BLOCKER** until corrected.)
5. **RLS/policy/grant drift:** manual changes in Dashboard removed protections or altered grants unexpectedly. (**BLOCKER/security risk**.)
6. **Plan/operational limits:** project paused, over quota, or auth limits hit (demo inconvenience, not a schema blocker but an availability blocker). (**BLOCKER for demo availability** until resolved.)
7. **Data sensitivity mismatch:** even if “test/demo only” now, if the project contains anything you would not want exposed via a public demo URL, reusing it is a **policy/blocker** decision. (**BLOCKER by choice** if unacceptable.)
8. **Unclear admin/bootstrap state:** no working admin/hospital profiles linked to demo Auth users prevents meaningful testing. (**BLOCKER for demo usability** until provisioned via approved steps such as `assign_role`.)

**Non-blockers by default (repo supports reuse):** repo migrations and code are designed to work with this Supabase/Postgres model (RLS + JWT GUCs + profiles). Reuse is the intended path unless one of the above applies.

## 10. Prioritized manual verification checklist (action order)

1. **P1 — Confirm project identity & URL:** correct project, `SUPABASE_URL` matches. (Stops wrong-project mistakes.)
2. **P2 — JWT strategy + claims:** prefer JWKS; verify `iss`/`aud`; set Render overrides only if needed. (Auth will fail otherwise.)
3. **P3 — Migration state 0001–0010:** confirm applied in order; verify 0005/0008/0009/0010 present/effective. (Security + correctness.)
4. **P4 — RLS/grants/role posture:** RLS enabled, policies/grants as expected, API DB role RLS-bound/no bypass, least privilege. (Security critical.)
5. **P5 — Auth redirects:** Site URL + Redirect URLs set to Vercel demo origin/paths. (Login/recovery broken if wrong.)
6. **P6 — Demo accounts/bootstrap:** ensure at least one admin and one hospital profile/user exist for testing (`assign_role` path understood).
7. **P7 — Post-deploy app smoke:** sign-in, role scoping, CORS/JWT errors handled cleanly, no secrets leaked.

## 11. Final recommendation

**Recommendation: REUSE EXISTING PROJECT** — **conditional** on passing the prioritized checks above.

Rationale (read-only, evidence-based):
- Repository migrations and backend implementation are explicitly aligned to this Supabase model (JWT verification via JWKS/HS256 with derived defaults, transaction-local JWT GUCs + `authenticated` role usage, RLS policies and helper functions defined in repo, `assign_role` for provisioning). This is the intended architecture.
- The project is stated to contain only test/demo data, which matches a university demo goal. No repo changes are required to “support” reuse.
- **However**, reuse is **not safe to assume** without manual verification of JWT claims/key strategy, Auth redirect URLs, hosted migration state (0001–0010), RLS/grants, and the `DATABASE_URL` role’s RLS/bypass posture. If any of P1–P5 fail and cannot be corrected quickly/appropriately for a demo, then **CREATE SEPARATE DEMO PROJECT** is the safer fallback (new project with migrations applied cleanly from repo, fresh demo data, controlled Auth config) — but that is a separate operational task not performed here.

**If you cannot complete P1–P5 before demo:** treat the demo as **at risk** (auth or data access will likely break) and prefer deferring the public demo or using a properly prepared separate demo project.

## 12. Constraints reaffirmed

- Read-only inspection only. No hosted data accessed or modified, no migrations/SQL run, no Supabase Dashboard changes made, no secrets/tokens/UUIDs/DB URLs printed, no code/env changes, no staging/commit/push.
- All existing untracked files preserved.