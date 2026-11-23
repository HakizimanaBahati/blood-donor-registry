# D-03D — Database Connection Security Audit (Read-Only)

## 1. Executive Summary

This audit reviews the Blood Donor Registry Django REST backend (with Next.js frontend and Supabase Postgres/Auth used as the intended platform) to determine whether PostgreSQL database access is compatible with Supabase Row Level Security (RLS) and whether tenant isolation (admin vs hospital, cross-hospital access) is enforced at the correct layer for a university/demo deployment on **Render (API) + Vercel (frontend) + Supabase (Postgres/Auth)**.

**What the source code shows (evidence-based):**
- Django connects using `DATABASE_URL` (`backend/config/settings.py`) with `conn_max_age=0` (no long-lived persistent connection pool in Django). In production (`DJANGO_DEBUG=false`) an unset `DATABASE_URL` is a hard startup failure; in debug-only fallback paths `TEST_DATABASE_URL` may be used locally.
- For requests that include a verified Supabase Bearer JWT, `SupabaseClaimsMiddleware` (`backend/authentication/middleware.py`) runs inside `transaction.atomic()`, sets Postgres transaction-local GUCs `request.jwt.claim.sub` and `request.jwt.claim.role='authenticated'` via `set_config(..., true)`, and executes `SET LOCAL ROLE authenticated`. This is the intended mechanism to align DB session context with RLS policies written for the `authenticated` role and helpers that read those claims.
- DRF authentication (`SupabaseJWTAuthentication`) verifies JWTs (JWKS preferred via `SUPABASE_JWKS_URL`/derived from `SUPABASE_URL`; HS256 only if explicitly configured) and resolves the application identity from `public.profiles` by the verified `sub`. App authorization (admin/hospital, hospital scoping) is enforced primarily in Django (permissions/views/services) using that profile; migrations also define RLS policies/helpers as a defense-in-depth layer.
- Supabase migrations (0001–0010 in repo) define `anon/authenticated/service_role` expectations, tables, helper functions `bdr_uid()`, `bdr_is_admin()`, `bdr_is_hospital()`, `bdr_hospital_id()`, triggers, RLS enablement and policies on `donors/hospitals/profiles/requests` (0005), plus hardening/revocations (0009/0010). These are **repo-defined** behaviors; hosted application is **not verified** here.

**Main security concerns (from this read-only review):**
- **RLS effectiveness is deployment-dependent.** Even with correct middleware behavior, if the `DATABASE_URL` login role is a **superuser** or has **`BYPASSRLS`**, Postgres will not enforce RLS for that role. Also if the login role cannot `SET ROLE authenticated` in the deployed environment, the middleware’s transaction-local role switch will fail or behave incorrectly.
- **External connection pooling (Supabase poolers/PgBouncer)** is not specified in repo code. Transaction/session pooling can affect whether `SET LOCAL ROLE`/GUC semantics are preserved as assumed; identity/session leakage risk cannot be ruled out without deployed topology verification.
- **Unauthenticated code paths:** middleware sets JWT claim GUCs and `SET LOCAL ROLE authenticated` only when a verified Bearer token exists. Requests without a verified token do not receive that RLS-oriented context; API-layer auth/permissions reject unauthorized access, but DB safety for any accidental DB work in that context depends on the login role being minimally privileged and RLS posture on that role context (not verified).

**Bottom line (decision):** **SAFE ONLY AFTER SPECIFIC CORRECTIONS** (and hosted verification). The codebase is structured to support RLS-aware access (verified JWT → transaction-local claim GUCs + `SET LOCAL ROLE authenticated`), but **hosted facts** (actual DB role attributes, applied migration/RLS/grants state, pooler mode, and end-to-end behavior) are **NOT VERIFIED** in this audit. You must confirm/implement the specific corrections listed in Section 11 before treating Render deployment as safe from an RLS/enforcement standpoint.

---

## 2. Scope and Safety Confirmation

### 2.1 Scope reviewed (read-only)
- Backend configuration: `backend/config/settings.py`, `backend/config/test_runner.py`, `backend/config/urls.py`, `backend/config/health.py` (context).
- Authentication/authorization stack: `backend/authentication/jwt.py`, `backend/authentication/authentication.py`, `backend/authentication/middleware.py`, `backend/authentication/permissions.py`, `backend/authentication/services.py`, `backend/authentication/models.py` (referenced), `backend/authentication/tests/test_middleware.py`, `backend/authentication/tests/test_rls.py` (behavioral expectations).
- Supabase migrations (repo): `supabase/migrations/0001_roles.sql`, `0002_tables.sql`, `0003_indexes.sql`, `0004_functions.sql`, `0005_rls.sql`, `0006_request_donor_link.sql`, `0007_fix_donors_phone_regex.sql`, `0008_fix_donors_phone_regex_literal_plus.sql`, `0009_harden_function_search_paths.sql`, `0010_revoke_rls_auto_enable.sql` (and `supabase/migrations/.gitkeep` listing context).
- Prior audit/report context: `docs/D-03A_PRODUCTION_CONFIGURATION_AUDIT.md`, `docs/D-03B_DEMO_DEPLOYMENT_PREPARATION.md`, `docs/D-03C_SUPABASE_DEMO_PREFLIGHT.md`, `docs/D-03E_HOSTED_READINESS_REPORT.md` (and related D-02/D-01 docs referenced in-repo context).

### 2.2 Safety confirmation (STRICTLY READ-ONLY)
- **No hosted Supabase database was connected to.** No hosted SQL executed. No migrations run. No database roles/grants/RLS/policies/functions modified in any hosted system by this audit.
- **No source code, settings, or environment files were modified.** No `.env` values were read from a live host context in this report; no secrets/tokens/passwords/JWTs/cookies/UUIDs/database URLs were printed.
- **No Git staging/committing/pushing/reset/stash/discard/clean performed.** Existing untracked files (including `backend/b05b7_r.py` and all listed `docs/D-02*`, `docs/D-03*` files present in the workspace) were preserved.
- **No hosting services created/deployed.** This is a documentation-only read-only audit output.
- Any mention of “local tests” or “database inspection” in this report refers to **safe, loopback-only, isolated** practices described elsewhere in repo docs; this audit did **not** perform hosted DB inspection.

**Classification:** **PASS** (audit performed under stated read-only constraints). Hosted verification remains **NOT VERIFIED**.

---

## 3. Database Connection Architecture

### 3.1 Connection source (evidence: `backend/config/settings.py`)
- Primary database configuration uses **`DATABASE_URL`** via `dj_database_url.parse(os.getenv("DATABASE_URL"), conn_max_age=0)`, assigned to `DATABASES["default"]`. `DATABASES["default"]["OPTIONS"]` defaults to `{}` (no explicit role, isolation level, or custom libpq options set in code).
- Behavior:
  - If `DJANGO_DEBUG` is false and `DATABASE_URL` is unset: raises `RuntimeError` (startup guard).
  - If `DJANGO_DEBUG` is true and `DATABASE_URL` is unset: falls back to `TEST_DATABASE_URL` (local/dev convenience) before failing. **Production must set `DATABASE_URL` explicitly.**
- **No alternate production DSN builders** (hardcoded URLs, second connection managers for the app DB) found in inspected application code paths. (`backend/config/test_runner.py` may override the test DB from `TEST_DATABASE_URL` in the test runner flow; this is test-only.)

**Finding:** **PASS** (source code) — Django uses `DATABASE_URL` as the sole production connection source in inspected code.  
**Hosted facts:** **NOT VERIFIED** (actual Supabase connection string type used in Render: direct Postgres vs Supavisor/pooler, and exact role encoded in that URL). This must be confirmed by deployment operators (do not print secrets).

### 3.2 Direct vs pooled connection (evidence + deployment note)
- Repo sets `conn_max_age=0` in `settings.py` (`dj_database_url.parse(..., conn_max_age=0)`), meaning **Django does not retain persistent connections across requests** via `CONN_MAX_AGE` pooling (connections are closed at request cycle end in the typical pattern). This reduces cross-request reuse risk on the Django side but **does not address external pooling** in front of Postgres.
- **No pooler configuration is present in repository code** (no PgBouncer parameters, no Supabase pooler mode selection in code). Whether the deployed `DATABASE_URL` is a **direct connection** to Postgres or a **Supabase pooler** (e.g. transaction/session pooling via Supavisor) is a **deployment choice** (Render env) and is **NOT VERIFIED** from repo.

**Finding:** **NEEDS CONFIGURATION / NOT VERIFIED** — Operators must document and verify the connection path (direct vs pooler) and pooler mode; the app’s transaction-local `SET LOCAL ROLE`/GUC pattern assumes careful semantics (see Section 6).

### 3.3 Middleware/request transaction wrapper (evidence: `backend/authentication/middleware.py`)
- `SupabaseClaimsMiddleware` is installed in `MIDDLEWARE` (`backend/config/settings.py`: `CorsMiddleware`, `SecurityMiddleware`, `SupabaseClaimsMiddleware`). For every request it:
  - Generates a debug request id and logs auth header presence/scheme (no token/secret values logged in shown logic).
  - If `Authorization: Bearer ...`, attempts `verify_access_token(token)`. On `SupabaseTokenError` sets `request.supabase_auth_error` and does not set a verified token (DRF returns 401 later as appropriate). On success sets `request.verified_token`.
  - Wraps the rest of the request in **`with transaction.atomic(): ...`** (unconditionally in current implementation). Inside that transaction, if a verified token exists it executes:
    1. `SELECT set_config('request.jwt.claim.sub', %s, true)`
    2. `SELECT set_config('request.jwt.claim.role', %s, true)` with value `'authenticated'`
    3. `SET LOCAL ROLE authenticated`
  Then calls `self.get_response(request)`. No global `ATOMIC_REQUESTS=True` is set in `settings.py`; atomicity is applied by middleware.

**Implication:** For authenticated requests with a verified JWT, database work performed during request handling occurs inside that transaction with transaction-local identity/role context set by the app. For requests without a verified token, the middleware still opens a transaction but does **not** set those GUCs/role changes.

**Finding:** **PASS** (behavior as coded). **NEEDS CONFIGURATION** risk if the login DB role cannot `SET ROLE authenticated` or is privileged/bypassing (see Sections 4–5).

---

## 4. Expected PostgreSQL Role and RLS Bypass Assessment

### 4.1 Roles defined in migrations (evidence: `supabase/migrations/0001_roles.sql`)
- Migration 0001 creates/ensures roles `anon`, `authenticated`, `service_role` (idempotent guards), grants `USAGE` on schema `public` to them, and sets default privileges for future objects created by `postgres` to grant `SELECT, INSERT, UPDATE, DELETE` on tables and `USAGE, SELECT` on sequences to `authenticated` and `service_role` in that context (comment notes Supabase provides roles; blocks make migration runnable elsewhere).
- **Important (from file comment/intent):** `service_role` is created with `NOINHERIT BYPASSRLS` in the DO block logic shown (exception handling notes Supabase may already have it). The Django API should **not** use a `service_role` connection for normal request handling.

### 4.2 RLS, grants, and helper execution model (evidence: `supabase/migrations/0004_functions.sql`, `0005_rls.sql`, `0009_harden_function_search_paths.sql`, `0010_revoke_rls_auto_enable.sql`)
- `bdr_uid()`: returns UUID from `request.jwt.claim.sub` or parsed from `request.jwt.claims` (`sub`); 0009 sets `search_path = public, pg_temp` (STABLE). (0004 defines initial form; 0009 redefines.)
- `bdr_is_admin()`, `bdr_is_hospital()`, `bdr_hospital_id()`: `SECURITY DEFINER`, `STABLE`, `search_path` set in 0004 (`public`); EXECUTE revoked from `PUBLIC`/`anon`, granted to `authenticated`, `service_role` (0004).
- `assign_role(...)`: `SECURITY DEFINER`, restricted; EXECUTE revoked from `PUBLIC/anon/authenticated`, granted to **`service_role` only** (intended for privileged provisioning, not normal Django API JWT flow).
- 0005: revokes broad privileges on `public.donors/hospitals/profiles/requests` from `anon, authenticated, PUBLIC`; grants specific privileges to `authenticated` (tables: `SELECT,INSERT,UPDATE,DELETE` on `donors,hospitals,requests`; `profiles`: `SELECT`, and `UPDATE` only on column `full_name`). Enables RLS on those tables and defines policies (summarized in Section 8). `rls_auto_enable()` revoked from client roles if present (0010).
- RLS policies rely on `bdr_uid()` and the `bdr_*` helpers and on the effective role being `authenticated` in the intended model (PostgREST-style), combined with JWT claim GUCs set by the app when using this Django pattern.

### 4.3 Expected PostgreSQL role for the Django API connection (source-code inference)
From code alone:
- **Connection identity is whatever `DATABASE_URL` provides** (login role/user in the connection string). The application **does not** set a fixed `ROLE` in Django `OPTIONS` and does not hardcode a role name in settings.
- At request time, for **verified-JWT requests**, the app issues `SET LOCAL ROLE authenticated` in the same transaction as request handling. This implies the **login role must be permitted to `SET ROLE authenticated`** (or an equivalent privilege model) in the deployed database.
- For **non-verified-token requests**, the app does **not** switch to `authenticated` and does not set claim GUCs; DB work (if any reached the DB layer in that context) would run as the **login role** with no app-set RLS claim context—this is dangerous if the login role is powerful.

### 4.4 RLS bypass assessment (what could bypass RLS)
- **Superuser:** bypasses RLS in PostgreSQL; using a superuser `DATABASE_URL` would defeat RLS regardless of middleware GUCs/role switching intent. **NOT acceptable.**
- **Role with `BYPASSRLS`:** bypasses RLS; same practical effect as superuser for RLS enforcement. **NOT acceptable.**
- **Login role lacks `SET ROLE authenticated` or behaves unexpectedly under pooler:** may cause middleware transaction errors or leave queries running as the wrong role; could undermine the intended `authenticated` RLS context. **Operational risk.**
- **Correct model (intended):** a **non-superuser, non-`BYPASSRLS`** login role used by Django that is allowed to assume/switch to the `authenticated` role context as implemented, with minimal privileges, so that RLS policies (and `bdr_*` helpers reading `request.jwt.claim.*` set by the app) can constrain access. This matches the “restricted backend role recommended in production” comments in middleware.

**Findings:**
- **NEEDS CONFIGURATION (hosted):** The deployment **must** provision/use a `DATABASE_URL` login role that is **not** superuser and **does not** have `BYPASSRLS`, and is permitted to `SET ROLE authenticated` for verified-request handling. This is **not enforced in repo** and is **NOT VERIFIED** for any hosted environment.
- **BLOCKED (cannot be proven here):** Whether the current/target Supabase project’s API role meets these attributes is **not verifiable** without hosted database inspection (forbidden by this audit). Operators must verify via controlled admin checks outside this read-only report workflow.
- **NOT VERIFIED:** Exact role name/attributes of the role embedded in any production `DATABASE_URL`.

---

## 5. Authentication and Database Identity Context

### 5.1 JWT verification and app identity resolution (evidence)
- `backend/authentication/jwt.py`: verifies Supabase access tokens (header sanity checks, algorithm allowlist including HS256/RS256/ES256, rejects `alg=none`, requires `exp/sub/iat`, verifies signature/audience/issuer). JWKS path uses `PyJWKClient` against `SUPABASE_JWKS_URL` (derived from `SUPABASE_URL` + `/auth/v1/.well-known/jwks.json` if unset); HS256 requires `SUPABASE_JWT_SECRET`. Returns `VerifiedToken(subject, claims)`; `sub` must be a valid UUID. Errors are sanitized/generic for clients in failure modes.
- `SupabaseJWTAuthentication` (`backend/authentication/authentication.py`): reuses `request.verified_token` if set by middleware, else verifies again. Resolves app user via `get_app_user(verified.subject)` (`backend/authentication/services.py`): looks up `Profile` by primary key `subject` (UUID), requires role in `{admin,hospital}`, returns an `AppUser` (id, full_name, role, hospital_id). If no valid profile/role, raises `PermissionDenied` (“No registry profile linked…”).
- `SupabaseClaimsMiddleware` sets `request.verified_token` and `request.supabase_auth_error` based on Bearer verification; it does **not** assign `request.user` (DRF authentication does). It does set DB context for verified tokens only.

### 5.2 Database identity context set for RLS (evidence)
- For verified tokens, middleware sets in the request transaction:
  - `request.jwt.claim.sub = verified.subject` (via `set_config(..., true)`)
  - `request.jwt.claim.role = 'authenticated'` (via `set_config(..., true)`)
  - `SET LOCAL ROLE authenticated` (transaction-local)
- `bdr_uid()` (0004/0009) reads `request.jwt.claim.sub` (or fallback from `request.jwt.claims` JSON) to return the UUID used by RLS policies and helper functions. Thus **Postgres-side identity for RLS is derived from the app-set transaction-local claim**, which is derived from the **verified JWT `sub`**—not from trusting a role claim inside JWT for app authorization decisions beyond the context string set by the app (`'authenticated'`).

### 5.3 Application-level authorization vs DB RLS (evidence)
- Permissions: `IsAuthenticatedUser`, `IsAdminUser`, `IsHospitalUser` (`backend/authentication/permissions.py`) gate access based on `request.user` (the resolved `AppUser` from profile). Views/services apply business rules (e.g. hospital scoping on requests/donors endpoints as implemented in app code) in addition to database constraints.
- RLS: migrations define policies on `donors`, `hospitals`, `profiles`, `requests` using `bdr_*` helpers and role `authenticated` expectations (0005). This provides a **defense-in-depth** backstop **if** RLS is enforced by Postgres for the connection role and if the session context (role + claim GUCs) is correctly established.

**Findings:**
- **PASS (code design):** Identity key for RLS context is taken from **verified JWT `sub`**, then mapped to app role/hospital via `profiles` lookup; middleware prepares RLS session variables consistent with that verified identity for the request transaction.
- **NEEDS CONFIGURATION / NOT VERIFIED:** Hosted ensures `DATABASE_URL` role is RLS-subject and can switch to `authenticated`; without that, the app’s RLS setup is ineffective or unsafe.
- **NOT VERIFIED:** Whether any code path performs DB queries outside the middleware-wrapped request transaction in a way that bypasses the intended context (not observed in inspected request flow; general Django usage patterns not exhaustively audited beyond inspected files).

---

## 6. Transaction and Connection Pooling Analysis

### 6.1 Transaction behavior (evidence)
- `transaction.atomic()` wraps the entire request handling in `SupabaseClaimsMiddleware` for **all** requests (including unauthenticated ones), with conditional setting of role/GUCs only when verified. This means:
  - Verified requests get `SET LOCAL ROLE authenticated` and local claim GUCs for the duration of that transaction (until commit/rollback at middleware end).
  - Unverified requests run in a transaction as the **login role** with no app-set JWT claim GUCs and no role switch to `authenticated` (relying on API-layer rejection before meaningful authorized work).
- No `ATOMIC_REQUESTS` setting in `settings.py`.

### 6.2 Django connection pooling (`conn_max_age`)
- `conn_max_age=0`: Django does not keep connections open across requests (per `dj_database_url.parse` option). This limits risk of leaking session state (role/GUCs) via Django’s persistent connection pool **across different request cycles managed by Django’s pooling**, but state set with `SET LOCAL`/`set_config(..., true)` is already transaction-scoped.

### 6.3 External pooling (Supabase/Supavisor or PgBouncer) — NOT VERIFIED
- Repository does **not** document pooler mode. Key risks (general, applicable to this design):
  - **Transaction pooling (common in some serverless/Postgres poolers):** server connections may be reassigned between transactions; `SET LOCAL` is transaction-scoped (fine). However, behavior of `SET ROLE` (session vs local semantics in practice depends on usage; middleware uses `SET LOCAL ROLE authenticated`) and pooler handling of role changes can be subtle. Some poolers do not support or restrict session-level role changes as expected. If the pooler resets state in unexpected ways or if the app assumes session persistence, context can be wrong.
  - **Session pooling:** a server connection may be reused across multiple client interactions; combined with `conn_max_age=0` on Django side you may still get varied server sessions, but the critical issue is ensuring no prior request’s role/GUC leaks. The middleware sets locals per request transaction (good), but any code that runs outside that transaction or any pooler that fails to isolate could leak.
- **Identity context leakage between requests:** **Plausible in misconfigured pooled environments**, especially if the login role is privileged or if pooler mode conflicts with `SET LOCAL ROLE` patterns. This is **NOT VERIFIED** without deployment topology (connection string type, pooler mode, Supabase project settings). Operators must validate with smoke tests (e.g. alternating authenticated requests for different users/hospitals and confirming isolation).

**Findings:**
- **PASS (code intent):** Transaction-local context + `conn_max_age=0` + per-request transaction wrap is a reasonable design to scope identity to the request.
- **NOT VERIFIED:** External pooler compatibility and absence of cross-request leakage in the deployed environment.
- **NEEDS CONFIGURATION:** Document pooler choice (direct vs transaction/session) and test RLS isolation under that choice; if pooler interferes with `SET ROLE`, redesign may be required (e.g. different role model) — **do not** relax RLS.

---

## 7. RLS Helper Function Review

### 7.1 `bdr_uid()` (`supabase/migrations/0004_functions.sql`, refined by `0009_harden_function_search_paths.sql`)
- Returns `coalesce(nullif(current_setting('request.jwt.claim.sub', true), '')::uuid, (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub')::uuid)`. `LANGUAGE sql STABLE`. 0009 sets `search_path = public, pg_temp` and redefines the function (body unchanged in effect described). 
- **Correctness for this app:** middleware sets `request.jwt.claim.sub` via `set_config(..., true)` for verified requests, so `bdr_uid()` should see the verified subject. Fallback to `request.jwt.claims` JSON supports alternate claim-passing styles if used elsewhere, but the Django app primarily uses the explicit GUC set by middleware.

**Classification (repo): PASS. Hosted behavior: NOT VERIFIED** (depends on migrations applied and GUCs actually set in the same transaction/context seen by Postgres for queries evaluated under RLS).

### 7.2 `bdr_is_admin()`, `bdr_is_hospital()` (`0004_functions.sql`)
- `SECURITY DEFINER`, `STABLE`, `search_path = public` (0004). Look up `public.profiles` by `bdr_uid()` and check `role`. EXECUTE granted to `authenticated`, `service_role`; revoked from `PUBLIC`/`anon`.
- These are the core helpers used by RLS policies in 0005 to distinguish admin vs hospital and to resolve hospital scope. They depend on `bdr_uid()` returning a non-null UUID that matches a `profiles.id`.

**Classification (repo): PASS (intent). Hosted: NOT VERIFIED** (profile rows, grants, and that the calling role/context is as expected).

### 7.3 `bdr_hospital_id()` (`0004_functions.sql`)
- `SECURITY DEFINER`, `STABLE`, `search_path = public`. Returns `profiles.hospital_id` for current hospital user (or NULL). Used in policies for hospitals scoping (e.g. requests filtered by `hospital_id = bdr_hospital_id()`).

**Classification (repo): PASS (intent). Hosted: NOT VERIFIED.**

### 7.4 `set_updated_at()` and triggers (`0004_functions.sql`, `0009_harden_function_search_paths.sql`)
- Trigger function hardened in 0009 to `search_path = public, pg_temp`, used on `donors`/`requests`. Not directly an RLS identity helper but part of migration hardening; **repo: PASS**, **hosted: NOT VERIFIED** if migrations not applied.

### 7.5 `assign_role(...)` (`0004_functions.sql`)
- `SECURITY DEFINER`, validates inputs, requires matching `auth.users` row, upserts `profiles`. EXECUTE revoked from `PUBLIC/anon/authenticated`, granted to `service_role` only. **Not used by the Django API’s normal JWT-authenticated request path** described here; used for privileged provisioning. **Repo: PASS (restricted). Hosted: NOT VERIFIED** (actual grants/state).

---

## 8. Admin and Hospital Tenant Isolation Assessment

### 8.1 What migrations define (evidence: `0002_tables.sql`, `0005_rls.sql`, `0006_request_donor_link.sql`)
- **Tables (relevant):** `profiles` (`id` references `auth.users`, `role` in `{admin,hospital}`, `hospital_id` required when role is `hospital`), `hospitals`, `donors`, `requests` (includes `requester_profile_id`, `hospital_id`, `donor_id` nullable FK added in 0006). Constraints enforce blood types, units, status, notes length, etc.
- **RLS enabled** on `donors`, `hospitals`, `profiles`, `requests` (0005). Grants: broad revokes from `anon/authenticated/PUBLIC` on these tables; `authenticated` granted `SELECT,INSERT,UPDATE,DELETE` on `donors/hospitals/requests`; `profiles` granted only `SELECT` and `UPDATE (full_name)` (column-level restriction).

#### 8.1.1 `donors` policies (0005, summarized)
- SELECT: allowed if `bdr_is_admin()` OR `bdr_is_hospital()` (authenticated context). (Hospitals can read donors for registry/search workflows per policy intent as written.)
- INSERT/UPDATE/DELETE: restricted to admin (`bdr_is_admin()`) with appropriate WITH CHECK on UPDATE.

#### 8.1.2 `hospitals` policies (0005, summarized)
- SELECT: allowed if admin OR `id = bdr_hospital_id()` (hospital users see only their associated hospital row as written).
- INSERT/UPDATE/DELETE: admin only (per migration comments/policy structure described).

#### 8.1.3 `profiles` policies (0005, summarized)
- SELECT: `id = bdr_uid() OR bdr_is_admin()`.
- UPDATE: only when updating own row (`id = bdr_uid()`) with same WITH CHECK; combined with column grant limiting updates to `full_name` (prevents role/hospital_id escalation via PostgREST/grant path as intended). No INSERT/DELETE policies shown (profile provisioning via `assign_role`/trusted processes per comments).

#### 8.1.4 `requests` policies (0005, summarized)
- SELECT/INSERT/UPDATE/DELETE: allowed if admin OR `hospital_id = bdr_hospital_id()` (hospital scoped to their own hospital). Comments note Django also enforces rules (defense in depth).

### 8.2 Django application-layer enforcement (evidence)
- `IsAdminUser` / `IsHospitalUser` and view/queryset logic (per repo patterns referenced in prior reports and common structure) restrict admin-only endpoints and scope hospital queries by `request.user.hospital_id`. This is **application-level** enforcement and runs in the same request context where middleware sets RLS GUCs/role for verified tokens.
- **Important:** Application filtering is **not equivalent** to database-enforced RLS if RLS is not enforced (e.g. bypassing role) or if queries are made in a different context. The codebase intends both layers.

### 8.3 Distinction required by this audit
- **Database-level enforcement (RLS):** depends on (a) migrations applied on hosted DB, (b) RLS enabled, (c) policies/grants as written, (d) connection role **not** bypassing RLS and able to assume `authenticated` context as used, (e) `bdr_uid()`/helpers seeing correct claim GUCs set by the app in the same effective transaction/context for those queries. **All (d),(e), hosted state of (a)–(c) are NOT VERIFIED here.**
- **Application-level enforcement:** present in Django (permissions, profile-based role/hospital, view logic). This is what currently gates most API behavior in practice but can be undermined by DB misconfiguration (bypassing role) or by bugs; RLS is the intended backstop.

### 8.4 Assessment against stated protections (repo intent vs hosted reality)
| Protection goal | Repo intent (migrations + app) | Source-code evidence | Hosted verification |
|---|---|---|---|
| Admin access to donor/hospital records (per policies) | Admin allowed by RLS on donors/hospitals (and app admin permissions) | 0005 policies + admin permission classes | NOT VERIFIED |
| Hospital access limited to own hospital record | Hospitals SELECT own hospital via `bdr_hospital_id()` policy; app also checks | 0005 hospitals policy + app checks | NOT VERIFIED |
| Hospital access limited to requests of that hospital | Requests scoped by `hospital_id = bdr_hospital_id()` or admin | 0005 requests policy + app scoping | NOT VERIFIED |
| Profile self-access and restricted updates (no role/hospital escalation via grants) | Profiles SELECT self-or-admin; UPDATE own row limited to `full_name` column grant | 0005 + middleware sets identity from verified `sub` | NOT VERIFIED (and depends on role not bypassing) |
| Prevent one hospital accessing another hospital’s records | RLS policies use `bdr_hospital_id()`; app enforces hospital_id scoping | 0005 + app logic | NOT VERIFIED |
| Prevent unauthorized role/hospital ownership changes | `assign_role` restricted to `service_role`; profile UPDATE grant limited to `full_name`; RLS policies restrict updates | 0004/0005 | NOT VERIFIED |

**Findings:**
- **PASS (design intent, repo):** Policies and app logic together aim for the listed protections; column-level grant on `profiles.full_name` is a concrete safeguard against trivial role escalation via table updates under `authenticated` grants as written.
- **NEEDS CONFIGURATION / NOT VERIFIED (hosted):** Actual enforcement requires applied migrations, RLS enabled, correct grants, non-bypassing login role, ability to `SET ROLE authenticated`, and correct claim GUC propagation in deployed pooling topology. Without these, **application-level filtering alone** is the effective control in practice but is weaker than intended defense-in-depth (and could be bypassed by any direct DB access using a privileged role).
- **NOT VERIFIED:** Whether hosted DB has any manual drift from repo migrations (extra policies, missing grants, different role attributes).

---

## 9. Render Deployment Security Implications

### 9.1 Components in scope
- **Render:** hosts Django backend (Web Service). Must run with `DJANGO_DEBUG=false`, strong `DJANGO_SECRET_KEY`, correct `DJANGO_ALLOWED_HOSTS` (exact Render hostname(s) including probe hosts as applicable), `DATABASE_URL` (secret), `CORS_ALLOWED_ORIGINS` set to exact Vercel HTTPS origins, Supabase JWT env configured (prefer JWKS).
- **Supabase:** hosts Postgres + Auth. Dashboard configuration (JWT `iss`/`aud`, Site URL/Redirect URLs) and DB role/pooler settings are external to repo and **NOT VERIFIED**.
- **Vercel:** hosts Next.js frontend with only public `NEXT_PUBLIC_*` vars; must not receive secrets.

### 9.2 Risks specific to this architecture
1. **Wrong `DATABASE_URL` role (highest severity):** if it is superuser or has `BYPASSRLS`, RLS is bypassed. The app’s middleware will still set GUCs/role in some cases, but PostgreSQL will not enforce policies for a bypassing role—this is a **critical security failure** for tenant isolation.
2. **Login role cannot `SET ROLE authenticated`:** middleware executes `SET LOCAL ROLE authenticated` for verified requests; if forbidden, the request transaction may error or run under wrong role, breaking functionality and potentially security assumptions. Must be ensured operationally.
3. **Pooler mode mismatch:** if using a pooler that is incompatible with the intended `SET LOCAL ROLE`/transaction semantics, identity context may not behave as tested locally. Requires validation.
4. **Unauthenticated requests:** middleware opens a transaction but does not set authenticated RLS context; any unintended DB access in unauthenticated paths would be as the login role. Login role must be minimally privileged and should not have broad data access outside what RLS+app logic assume (and RLS won’t help if role bypasses).
5. **Migrations/RLS drift on hosted Supabase:** if 0001–0010 not fully applied or altered, helpers/policies/grants may be missing/inconsistent, breaking isolation or causing errors. **NOT VERIFIED**.
6. **JWT/JWKS misconfiguration:** could allow auth failures (availability) or, if mis-set badly in other systems, security issues; code prefers JWKS and verifies `iss`/`aud`/alg—correct env on Render and matching Supabase project config are required (**NOT VERIFIED** live).
7. **CORS/redirects:** misconfiguration affects demo usability/security posture of the frontend flow but is not the DB RLS mechanism; still required for correct auth UX (covered in D-03A/D-03B).

### 9.3 Safest database connection approach for this university demo (without weakening RLS)
**Recommended (minimum safe posture), to be verified/configured by operators:**
- Use a **dedicated PostgreSQL login role** for the Django API (not superuser, not `BYPASSRLS`, not the migration/owner role used for applying schema changes in production workflows unless strictly controlled). Grant only the privileges necessary for the app’s operations consistent with repo migrations’ intent (and with RLS relied upon under the `authenticated` role context model).
- Ensure the login role has **privilege to `SET ROLE authenticated`** (or the equivalent mechanism used) so the middleware can switch into the `authenticated` role context for verified requests. (Exact grant/role membership depends on your Postgres/Supabase setup; this is an operational requirement.)
- Prefer a connection path whose behavior is **well understood** for `SET LOCAL ROLE` and transaction-local GUCs. If using Supabase poolers, validate with tests that RLS isolation holds (hospital A cannot see hospital B data via API) under the chosen pooler mode; if issues arise, prefer a topology/connection choice compatible with the current app design **rather than** disabling RLS or using a bypassing role.
- Keep `DATABASE_URL` as the only app DB credential source in Render (secret). Never expose it to the frontend.
- Continue using **JWKS-based verification** (RS256/ES256) for Supabase JWTs as configured in code/env, avoiding HS256 secrets unless unavoidable and never substituting service keys.
- Apply and keep migrations 0001–0010 in sync with repo intent on the hosted database (via an approved migration process), ensuring RLS remains enabled and policies/grants intact.

**Explicitly do NOT:** use a superuser or `BYPASSRLS` role “to make it work”; do not remove RLS or policies to unblock demo issues; do not move authorization solely to app code while ignoring DB role hardening.

---

## 10. Findings and Evidence

### 10.1 Evidence classification key
- **Source-code evidence:** direct inspection of files listed in Scope (authoritative for what code does).
- **Repo migration evidence:** SQL files in `supabase/migrations/0001`–`0010` (authoritative for intended schema/RLS/functions).
- **Hosted database facts:** **NOT VERIFIED** in this audit (no access). Any statement about live Supabase/Render state is an operational requirement/checklist item.

### 10.2 Findings table

| ID | Finding | Classification | Evidence (source) | Notes |
|---|---|---|---|---|
| F1 | Django production DB connection is sourced from `DATABASE_URL` with `conn_max_age=0`; debug may fall back to `TEST_DATABASE_URL` only when `DEBUG` true. | **PASS** | `backend/config/settings.py`, `backend/config/test_runner.py` (test-only override) | Production requires `DATABASE_URL` or startup fails when debug false. |
| F2 | `SupabaseClaimsMiddleware` sets transaction-local `request.jwt.claim.sub`, `request.jwt.claim.role='authenticated'`, and `SET LOCAL ROLE authenticated` inside `transaction.atomic()` for verified Bearer tokens; runs for all requests (sets only when verified). | **PASS** | `backend/authentication/middleware.py`, `backend/config/settings.py` (middleware order) | Intended to align with RLS model; depends on login role permissions and no bypass. |
| F3 | JWT verification prefers JWKS (derived from `SUPABASE_URL`) with RS256/ES256/HS256 allowed; HS256 requires secret; issuer/audience defaulted/overridable. App roles come from `profiles` lookup by verified `sub`, not trusted from JWT role claims for app authorization. | **PASS** | `backend/authentication/jwt.py`, `authentication.py`, `services.py` | Hosted `iss`/`aud`/key strategy **NOT VERIFIED**. |
| F4 | Migrations define `bdr_uid()`, `bdr_is_admin()`, `bdr_is_hospital()`, `bdr_hospital_id()`, SECURITY DEFINER helpers with EXECUTE grants to `authenticated`/`service_role` (and `assign_role` restricted to `service_role`), RLS enabled on core tables with policies/grants in 0005, hardening in 0009/0010. | **PASS** (repo intent) | `supabase/migrations/0001,0004,0005,0009,0010` | Hosted application of these migrations and current grants/policies **NOT VERIFIED**. |
| F5 | Hosted `DATABASE_URL` login role is non-superuser, has no `BYPASSRLS`, and can `SET ROLE authenticated` as required by middleware design. | **NEEDS CONFIGURATION / NOT VERIFIED** (hosted) | Inferred from F2,F4 and migration roles model; no repo enforcement | **Critical:** if false, RLS is bypassed or behavior breaks. Must be verified by operators (no hosted access in this audit). |
| F6 | Hosted migration/RLS/grant state matches repo (0001–0010 applied, policies/grants intact, no drift). | **NOT VERIFIED** | Repo files only | Requires manual/Supabase inspection outside this read-only audit. |
| F7 | External connection pooling (Supavisor/PgBouncer mode) is compatible with transaction-local `SET LOCAL ROLE` and claim GUCs; no cross-request identity leakage. | **NOT VERIFIED** | Code uses transaction-local + `conn_max_age=0`; no pooler config in repo | Must validate with deployed topology and smoke tests. |
| F8 | Unauthenticated requests: no JWT claim GUCs and no `SET ROLE authenticated` set by middleware; DB safety depends on login role being minimally privileged and API-layer auth blocking unauthorized actions. | **NEEDS CONFIGURATION** (risk) | `backend/authentication/middleware.py` | Login role must not be privileged/bypassing; rely on defense-in-depth carefully. |
| F9 | Tenant isolation (admin vs hospital, cross-hospital requests/hospitals/profiles constraints) is enforced by both Django app logic and RLS policies in repo; RLS is intended as backstop. | **PASS** (design intent) + **NEEDS CONFIGURATION/NOT VERIFIED** (effectiveness) | Views/permissions/services patterns (referenced in reports) + 0005 policies | Application filtering alone is not equivalent to DB RLS if role bypasses or context wrong. |
| F10 | Render/Vercel/Supabase deployment configuration (envs, redirects, allowed origins, pooler choice) is correctly set for the demo and aligns with code assumptions. | **NEEDS CONFIGURATION / NOT VERIFIED** | D-03A–D-03C/D-03E guidance | Operational checklist items remain open until deployed and tested. |

---

## 11. Required Corrections, if any

The following are **required corrections/configurations** (do **not** implement here without approval). They are the minimum needed to make the current architecture **safe** for Render demo deployment in light of this audit:

1. **Harden the `DATABASE_URL` login role (mandatory):**
   - Ensure the role is **not** a superuser and **does not** have `BYPASSRLS`.
   - Ensure the role has permission to **`SET ROLE authenticated`** (or the exact mechanism required so that `SET LOCAL ROLE authenticated` succeeds in the middleware transaction for verified requests).
   - Apply **least privilege**: grant only what the application needs consistent with migrations’ intended `authenticated` grants and RLS model. Do **not** use `service_role` credentials for the Django API connection.
2. **Verify hosted migration and RLS state (mandatory):**
   - Confirm Supabase Postgres has migrations **0001–0010 applied in order** (especially 0005, 0008/0007 corrections as present in repo intent, 0009, 0010).
   - Confirm RLS enabled on `donors`, `hospitals`, `profiles`, `requests`; policies/grants match repo 0005 intent (including `profiles` update restricted to `full_name` column grant).
   - Confirm `assign_role` EXECUTE is restricted to `service_role` only (per 0004).
3. **Verify and document connection/pooling behavior (mandatory before relying on isolation):**
   - Identify whether `DATABASE_URL` uses a **direct** connection or a **Supabase pooler** and the **pooler mode** (transaction/session). Document it.
   - Test that verified requests set effective RLS context as intended (no cross-tenant data leakage between hospital users/admin flows). If pooler mode breaks `SET LOCAL ROLE` semantics, choose a compatible connection strategy or adjust the design (approved change) — **never** by enabling bypassing roles or disabling RLS.
4. **Enforce secrets and env hygiene (operational, mandatory):**
   - Render: `DATABASE_URL`, `DJANGO_SECRET_KEY`, and (only if used) `SUPABASE_JWT_SECRET` in secret store; `DJANGO_DEBUG=false`; correct `DJANGO_ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, Supabase JWT/JWKS envs. No `TEST_DATABASE_URL` on Render.
   - Vercel: only public `NEXT_PUBLIC_*` keys; `NEXT_PUBLIC_ALLOW_DEV_LOGIN=false` for demo; never service/secret keys.
5. **Validate JWT/JWKS and Auth redirects against the deployed Vercel origin (mandatory for demo correctness):**
   - Confirm Supabase project URL, `iss`/`aud` (or overrides), and JWKS reachability from Render; set Supabase Auth Site URL and Redirect URLs to exact Vercel demo origin/paths. (This is not a DB RLS fix but affects whether verified tokens flow into the RLS context path.)

**If any of (1)–(3) cannot be satisfied:** do **not** deploy for any use where tenant isolation matters; for a throwaway demo only proceed with explicit written risk acceptance that database-level RLS enforcement is **not verified** and the login role may be the effective boundary (undesirable). This audit recommends **against** that path.

---

## 12. Final Deployment Recommendation

### 12.1 Decision
**SAFE ONLY AFTER SPECIFIC CORRECTIONS**

### 12.2 Evidence behind the decision
- **Positive (repo/source):** The codebase implements a coherent, RLS-oriented pattern: verified Supabase JWTs → transaction-local `request.jwt.claim.sub/role` + `SET LOCAL ROLE authenticated` in `transaction.atomic()` (middleware), app authorization derived from `profiles` by verified `sub`, and repo migrations define RLS policies/helpers/grants intended to enforce tenant/admin rules. Security-minded settings (env-driven secrets/hosts/CORS/CSRF posture, no secrets in code) and defense-in-depth intent are present.
- **Negative / blocking gaps (hosted, not verifiable here):** There is **no in-repo guarantee** that the deployed `DATABASE_URL` role is non-superuser and non-`BYPASSRLS`, nor that it can `SET ROLE authenticated`; hosted migration/RLS/grant state may differ from repo; external pooler behavior is unknown; unauthenticated request paths do not set the authenticated RLS context (so login-role privileges must be minimal). These are **operationally decisive** for whether RLS actually enforces isolation.
- **Conclusion:** Until corrections in Section 11 (especially role hardening, migration/RLS verification, and pooler/context validation) are completed and evidenced by operators, **deploying to Render with the current unverified hosted DB role/policy state is not safe to call “RLS-enforcing.”** After those corrections and successful end-to-end smoke tests (including cross-hospital isolation checks), the architecture is **supportable** for a university/demo deployment **with conditions** documented in D-03E; this audit does **not** claim production/hospital readiness.

**One-line summary:** The design is directionally correct in code, but **hosted database role/RLS/pooling facts are unverified** — proceed to Render configuration/deployment **only after** the specific corrections above are applied and validated.

---

## Appendix — Quick reference (no secrets)
- DB entrypoint: `backend/config/settings.py` (`DATABASE_URL`, `conn_max_age=0`, middleware list).
- RLS context setter: `backend/authentication/middleware.py` (`transaction.atomic`, `set_config` for `request.jwt.claim.sub`/`role`, `SET LOCAL ROLE authenticated`).
- JWT verification: `backend/authentication/jwt.py`; auth class: `backend/authentication/authentication.py`; app identity: `backend/authentication/services.py`.
- RLS/migrations: `supabase/migrations/0001_roles.sql`–`0010_revoke_rls_auto_enable.sql` (focus: 0004, 0005, 0009, 0010).