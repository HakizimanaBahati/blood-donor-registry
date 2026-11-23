# D-03F — Database Security Remediation Planning (Read-Only)

Date: 2026-11-23  
Project: Blood Donor Registry  
Basis: `docs/D-03D_DATABASE_CONNECTION_SECURITY_AUDIT.md` (Section 11: “Required Corrections, if any”) and repository evidence (`backend/config/settings.py`, `backend/authentication/middleware.py`, `backend/authentication/jwt.py`, `backend/authentication/authentication.py`, `backend/authentication/services.py`, `supabase/migrations/0001_roles.sql`–`0010_revoke_rls_auto_enable.sql`, prior D-03A–D-03E).  
Status: **Planning only. No implementation, no hosted access, no SQL executed, no changes made.**

## Safety and scope confirmation

- **Read-only.** No connection to hosted Supabase/Postgres. No SQL executed against any database (hosted or local) as part of this plan’s authoring beyond citing repo files.
- **No changes.** No code, settings, `.env`, migrations, database roles/grants/RLS/functions, hosting services, or deployments modified.
- **No secrets printed.** This document contains no database URLs, passwords, tokens, UUIDs, JWTs, cookies, or other credentials.
- **Git hygiene.** No staging, commit, push, reset, stash, discard, or clean. All existing untracked files preserved (including `backend/b05b7_r.py` and prior `docs/D-02*`/`docs/D-03*` reports).

This plan translates each required correction from **D-03D Section 11** into actionable remediation steps, validation procedures, and approval gates for an authorized operator to execute later (with approval).

---

## Executive summary (what this plan addresses)

D-03D concluded **“SAFE ONLY AFTER SPECIFIC CORRECTIONS”** for Render deployment from a DB/RLS safety perspective. The uncertainties and risks are **deployment-hosted** (role attributes, applied migration/RLS/grants state, Supabase connection/pooler behavior, JWT/redirect wiring impacts on the authenticated path) and must be resolved by operators with appropriate access. This document:

- Restates the **required corrections** from D-03D §11 as a structured remediation backlog.
- Answers the explicit questions in the request (role membership for `SET LOCAL ROLE authenticated`, superuser/BYPASSRLS, least privilege, pooler compatibility with transaction-local role + JWT claim GUCs, unauthenticated safety, verification of tenant/RLS isolation and identity non-leakage, hosted migration/grant/RLS verification requirements).
- Provides **exact proposed corrections (descriptive)**, **affected files/settings/Supabase objects**, **security implications**, **validation procedures** (manual/operational; no SQL strings that would be run here except described checks conceptually), and **whether explicit administrator approval is required** for each.
- Ends with a **recommended implementation order** and a **list of approvals needed**.

---

## Context facts (repo evidence used in planning)

- **App DB connection:** `backend/config/settings.py` uses `DATABASE_URL` via `dj_database_url.parse(..., conn_max_age=0)`. Prod requires `DATABASE_URL` when `DJANGO_DEBUG=false`; debug may fall back to `TEST_DATABASE_URL` only locally.
- **Request DB context (verified JWT only):** `backend/authentication/middleware.py` runs every request inside `transaction.atomic()`. If a verified Bearer token exists, it sets (transaction-local via `set_config(..., true)`):
  - `request.jwt.claim.sub = <verified.subject>`
  - `request.jwt.claim.role = 'authenticated'`
  then executes `SET LOCAL ROLE authenticated`, calls the view, then commits/rolls back the transaction. Unverified/no-token requests do **not** set these and do **not** switch role in this path (they proceed under the **login role** of `DATABASE_URL`, still inside that middleware transaction).
- **Identity/authorization split:** JWT verified in app (`backend/authentication/jwt.py`), app user resolved from `public.profiles` by verified `sub` (`backend/authentication/services.py`), DRF permissions enforce app roles/scoping; RLS helpers in migrations read claim GUCs (`bdr_uid()` from `request.jwt.claim.sub` or fallback JSON) and policies assume `authenticated` role context in the intended model (`supabase/migrations/0004_functions.sql`, `0005_rls.sql`, `0009_harden_function_search_paths.sql`).
- **Migrations (repo):** 0001 defines roles `anon`, `authenticated`, `service_role` (and grants/schema defaults); 0005 enables RLS/grants/policies on `donors/hospitals/profiles/requests`; `assign_role` is `SECURITY DEFINER` granted only to `service_role` (0004). 0010 revokes `rls_auto_enable` from client roles if present.
- **Pooler not configured in repo:** No PgBouncer/Supavisor mode settings in code; behavior depends on the connection string/hosting choice (Supabase direct vs pooler). `conn_max_age=0` in Django reduces Django-side persistent reuse but does not govern external poolers.
- **Unauthenticated API behavior:** DRF requires authenticated app user for protected endpoints (per `REST_FRAMEWORK` defaults); middleware still opens a transaction for all requests. Any accidental DB work in unauthenticated paths would run as the **login role** with no app-set `authenticated` context—**high risk** if login role is privileged/bypassing.

---

## D-03D Section 11 Required Corrections → Remediation items (mapped)

This plan treats D-03D §11 as the source checklist. Each item below is expanded into a “Correction plan” entry with the requested fields.

### Correction 1 — Harden the `DATABASE_URL` login role (mandatory)

#### 1.1 Root cause or uncertainty
- **Uncertainty (hosted, not verifiable here):** The PostgreSQL login role used by `DATABASE_URL` in Render may be a superuser, may have `BYPASSRLS`, may lack permission to execute `SET ROLE authenticated` (or equivalent) in the deployed Postgres/Supabase environment, and may have excessive privileges beyond what the app needs under the intended RLS + `authenticated`-context model. Repo does not enforce or record these attributes.
- **Root cause risk:** Any of the above breaks the intended security model: superuser/BYPASSRLS defeats RLS; inability to `SET ROLE authenticated` causes middleware `SET LOCAL ROLE authenticated` to fail (transaction error) for verified requests or leaves requests in the wrong role; excess privileges increase blast radius if app logic is bypassed or misused.

#### 1.2 Exact proposed correction (descriptive; no SQL executed here)
1. **Provision or select a dedicated API login role** in the target Supabase/Postgres project (separate from migration owners/service_role credentials used operationally elsewhere, and **not** the `service_role` API key/role used by Supabase dashboard service operations except by explicit, controlled design—do not reuse `service_role` for the Django `DATABASE_URL`).
2. **Role attributes (required):**
   - `LOGIN` enabled for this role (for `DATABASE_URL`).
   - **Not a superuser.** (`NOSUPERUSER`.)
   - **Does not have `BYPASSRLS`.** (ensure `NOBYPASSRLS` / equivalent; verify attribute.)
   - **Membership/privilege for role switching:** grant the ability to **`SET ROLE authenticated`** (e.g. make the login role a member of the `authenticated` role/group as appropriate in PostgreSQL/Supabase conventions), because the app executes `SET LOCAL ROLE authenticated` for verified requests (`backend/authentication/middleware.py`). (See §2 below for details.)
   - **Connection/database permissions:** allowed to connect to the intended database and use schema `public` as needed by the app (consistent with existing grants model).
3. **Least privilege (minimum necessary), aligned with repo intent:**
   - Do **not** grant broad owner/superuser/table owner powers to this role beyond what is required.
   - Rely on existing migrations’ grant model for the `authenticated` context: 0005 revokes broad access and grants `authenticated` specific privileges on `donors/hospitals/requests` (SELECT/INSERT/UPDATE/DELETE as written) and on `profiles` `SELECT` plus `UPDATE (full_name)` only. Therefore the **effective** data access for authenticated application traffic should be constrained by (a) switching to `authenticated` role in-transaction (middleware) plus (b) RLS policies and (c) those grants. The **login role** should have the minimal privileges needed to: connect, use schema, execute required functions/triggers behavior as allowed, and to `SET ROLE authenticated`. Avoid granting table DML directly to the login role if the design intends enforcement via the switched `authenticated` role context—**this must be reconciled carefully** with how Supabase/Postgres roles are modeled (Supabase commonly treats `authenticated` as a role used by PostgREST/JWT; the Django app is simulating that by setting the role). The operator must choose a model that is **secure and compatible** with the current middleware behavior (see §6 on poolers and §4 on verification). A safe default is: login role is a non-privileged role that is a member of `authenticated` (and/or has `SET ROLE authenticated`) and does **not** have direct broad table grants bypassing the intended model; however, the exact grant matrix must be validated against actual runtime queries (Django ORM may issue statements that require privileges under the active role). **This is an operational design decision requiring approval** (see §“Approvals needed”). 
4. **Do not use `service_role`:** `DATABASE_URL` must not use Supabase `service_role` credentials/role for normal API traffic (per repo: `assign_role` is granted to `service_role`; normal JWT flow uses app profiles). Using `service_role` would typically bypass RLS and is unacceptable.
5. **Rotate/replace credentials** only through approved secure processes (out of scope to perform here); the “correction” is the role attribute/privilege posture and correct `DATABASE_URL` usage.

#### 1.3 Files or Supabase settings affected
- **Supabase/Postgres (hosted):** database role definitions (create/alter role), role memberships (grant membership/role so login role can assume `authenticated` context as designed), privileges on schema `public`, privileges/attributes related to `SET ROLE`, and the `DATABASE_URL` secret/value stored in **Render** environment (and nowhere else committed).
- **Render (dashboard/env):** `DATABASE_URL` (secret) updated to point to the corrected role/connection string.
- **Repo/files:** **None required by the correction itself** unless documentation is updated later (this plan does not change repo). No code changes implied by this correction except possibly **not applicable**; current code assumes `SET LOCAL ROLE authenticated` succeeds when verified (middleware). If a different strategy is adopted (e.g. never set role, rely only on GUCs + RLS policies written differently), that would be a **code + migration design change** (out of scope here and requires separate approval).
- **Supabase Dashboard:** review project “Database” connection settings only to understand whether direct or pooler URLs are provided (informational); **do not** change production data.

#### 1.4 Security implications
- **If done correctly:** Reduces risk of RLS bypass (no superuser/BYPASSRLS), limits blast radius (least privilege), preserves intended defense-in-depth (RLS + app authz) when combined with correct middleware context.
- **If done incorrectly:** Can break the app (cannot `SET ROLE authenticated`, wrong privileges causing 500s) or silently weaken security (still bypassing). Using `service_role` in `DATABASE_URL` is a severe regression.
- **Trade-off:** Tightening privileges may require careful validation of all Django ORM operations and any raw SQL; over-restricting without understanding grants can cause outages. Under-restricting (e.g. leaving bypass) leaves tenant isolation ineffective.

#### 1.5 Validation procedure (no SQL executed in this plan; describe checks)
Perform by an authorized operator with DB admin access (separate from app login role), **in a non-production-like risk context only if explicitly approved**; prefer staging/demo validation:
1. **Attribute checks (conceptual):** Confirm the API login role is **not** superuser and **does not** have `BYPASSRLS`. Confirm it can connect to the intended database.
2. **Role-switch check:** From a session authenticated as the API login role (or equivalent test method), verify that executing `SET ROLE authenticated` (or the transaction-local equivalent used in practice) is permitted **without** elevating privileges inappropriately. Confirm that after switching to `authenticated`, the role’s effective privileges align with expectations (and RLS applies where intended) for the app’s queries.
3. **App smoke tests (after Render deploy/config):**
   - Deploy backend with the new `DATABASE_URL` pointing to the corrected role.
   - Verify `/health` responds (if it touches DB in that check context—repo shows health view behavior; confirm in practice) and that authenticated API calls work for a valid user.
   - Verify behavior when an invalid/missing token is sent: API must reject (401/403 as designed); confirm no data leakage and no unexpected privilege escalation path.
4. **Negative tests (controlled):** Attempt (in a safe test context) operations that should be forbidden by RLS/grants under `authenticated` to confirm enforcement is active (see §7–§8).
5. **Document outcomes** (sanitized) in an internal runbook/note; do not paste secrets.

#### 1.6 Whether explicit administrator approval is required
**Yes.** Creating/altering database roles, changing role memberships/privileges, and rotating/updating `DATABASE_URL` in Render are **privileged operational actions** that affect security posture and availability. Approval required from the project owner/admin (and ideally a second reviewer for production/demo data environments). Any change that would alter the intended role model (e.g. abandoning `SET ROLE authenticated` in favor of a different approach) requires **separate architectural approval**.

---

### Correction 2 — Verify Supabase connection method and pooler compatibility with transaction-local `SET ROLE` and JWT claim settings

#### 2.1 Root cause or uncertainty
- **Uncertainty:** Repo does not specify direct vs Supabase pooler (Supavisor) connection strings or pooler mode (session vs transaction pooling). The app relies on:
  - `SET LOCAL ROLE authenticated` inside a request-wrapping `transaction.atomic()` (transaction-local role change in Postgres terms for that transaction scope).
  - `set_config('request.jwt.claim.sub', ..., true)` and `set_config('request.jwt.claim.role', ..., true)` with `is_local = true` (transaction-local GUCs).
- **Risk:** In **transaction pooling**, server connections are reassigned between transactions in many implementations; `SET LOCAL` is fine within a transaction but poolers may interfere with certain session commands or with role changes depending on implementation. In **session pooling**, connections persist longer; combined with app behavior this is usually safer for session/role state than transaction pooling for some patterns, but still must be validated. Some poolers also have limitations around `SET ROLE`. If the pooler resets state unexpectedly or does not preserve the intended semantics, RLS context (`bdr_uid()` reading GUCs, effective role) can be wrong → **authorization bypass or broken access**.

#### 2.2 Exact proposed correction (descriptive)
1. **Inventory the deployed connection method:**
   - Identify the exact `DATABASE_URL`/connection string used by Render (direct Postgres hostname/port vs Supabase pooler endpoints such as Supavisor pooler URLs). This is a **configuration lookup** (operator action), not a code change.
   - Record (internally, sanitized) whether it is direct connection or pooler, and the **pooler mode** if pooler is used (transaction vs session), per Supabase project settings/documentation for that project.
2. **Preferred approach for this app design (planning recommendation):**
   - Prefer a connection strategy that is **compatible with per-request transaction-local `SET ROLE authenticated` and transaction-local `set_config` GUCs** as implemented. In practice, **session pooling** is often more compatible with session/role changes than aggressive transaction pooling, but this depends on Supabase’s current pooler behavior—**must be validated**. **Direct connections** (if used carefully, noting Supabase direct connection limits) avoid pooler-induced quirks but have other operational constraints.
   - **Do not** choose a pooler mode that silently breaks role switching or GUC visibility for RLS helpers.
3. **If pooler is required/used:** validate behavior explicitly (see validation). If validation shows incompatibility, **do not** weaken security (do not use bypassing role); instead consider: (a) switch to a compatible connection mode if available, (b) redesign (separate approved project) such as setting GUCs/role via a different mechanism compatible with pooling, or (c) accept demo risk only with explicit approval—**not recommended**.
4. **Document the decision:** record chosen connection method and pooler mode and the validation results in an internal ops note (no secrets).

#### 2.3 Files or Supabase settings affected
- **Render:** `DATABASE_URL` value (secret/config). May also require adjusting related connection parameters only if supported/documented by Supabase and the app stack (no repo changes implied).
- **Supabase Dashboard/Project settings:** connection pooling configuration (pooler enablement/mode), if changed by operators (admin action). **No repo files.**
- **Repo:** None for the correction itself; if a redesign is later approved, code/migrations could be affected (out of scope).

#### 2.4 Security implications
- **Correct choice + validation:** preserves RLS context integrity across requests under pooling.
- **Wrong pooler mode:** can cause `SET ROLE`/GUC behavior to be ineffective or inconsistent → potential **authorization bypass** (queries run under wrong role/context) or **availability** issues (errors). Silent failures are the worst case.
- **Over-reliance on direct connections:** may hit connection limits in hosted environments; not a security fix by itself.

#### 2.5 Validation procedure
1. **Confirm topology:** operator states connection type and pooler mode (sanitized record).
2. **Functional smoke (after deploy with that config):** sign in as a valid hospital user and perform allowed reads/writes; repeat for admin. Confirm no 500s attributable to role/GUC issues.
3. **RLS isolation tests (see §7):** execute the two-hospital + admin scenarios described in §7. If any cross-tenant access occurs where it should not, **treat as a blocker** (possible pooler/context issue or role/RLS issue).
4. **Leakage test (see §8):** perform rapid interleaved requests for different identities and verify no cross-contamination of data/results in observed API responses (see §8 for details).
5. **If anomalies found:** capture sanitized logs/observations (no tokens/secrets) and stop demo expansion; do not proceed to “safe” claim until root cause addressed.

#### 2.6 Whether explicit administrator approval is required
**Yes, for changes to Supabase pooler/project connection settings and for any decision to change `DATABASE_URL` topology.** Validation tests can be performed by operators with appropriate test accounts, but **changing production/demo pooler settings** is an admin/owner action. If redesign is required, that needs **architectural approval** in addition.

---

### Correction 3 — Validate and enforce unauthenticated request safety (DB layer)

#### 3.1 Root cause or uncertainty
- **Root cause:** Middleware sets authenticated RLS context (`sub`, `role='authenticated'`, `SET LOCAL ROLE authenticated`) **only** when a verified Bearer JWT is present. For unauthenticated requests, the same middleware transaction runs as the **login role** of `DATABASE_URL` with no app-set claim GUCs. API-layer DRF permissions should reject unauthorized access, but:
  - Any code path that accidentally performs DB queries for unauthenticated requests runs with login-role privileges.
  - If the login role is privileged/bypassing, this is a serious risk.
  - Even if not bypassing, RLS policies written for `authenticated` + `bdr_uid()` may behave unexpectedly without GUCs (helpers may return NULL), which could be confusing; the primary protection must be **application rejection + minimal login role**.

#### 3.2 Exact proposed correction (descriptive)
1. **Ensure login role is minimal (ties to Correction 1):** the `DATABASE_URL` role must not have privileges to read/write sensitive domain tables outside the tightly controlled intended model. Prefer a model where meaningful data access requires the `authenticated` role context established by middleware for verified users; the login role alone should have **no broad data access** to `donors/hospitals/profiles/requests` beyond what is strictly necessary (and ideally none for those tables). This must be compatible with Django’s behavior (migrations, connection setup)—requires careful design and validation.
2. **Defense in depth (application):** keep DRF `DEFAULT_PERMISSION_CLASSES` requiring authentication for protected routes (current `IsAuthenticatedUser` default) and explicit permissions on views. Do not introduce endpoints that perform sensitive DB reads for anonymous users without review.
3. **Optional (stronger, requires design approval):** introduce a DB-level guard pattern (e.g. role that cannot access app tables until switched, or use of separate roles) — **out of scope to implement here**; listed only as a possible future direction if Correction 1 model proves insufficient.
4. **Operational rule:** never grant the API login role superuser/BYPASSRLS or table owner rights over RLS-protected domain tables.

#### 3.3 Files or Supabase settings affected
- **Supabase/Postgres:** login role privileges/grants on `public` schema and on domain tables/functions as per chosen model.
- **Render:** `DATABASE_URL` unchanged in name but its role backing must be corrected (Correction 1).
- **Repo:** typically no changes if using the current middleware model; any guardrails added in code would require changes (approval). This plan assumes repo unchanged.

#### 3.4 Security implications
- **Correct:** unauthenticated requests are blocked at API layer and cannot leverage powerful DB credentials even if a bug allows a query to run.
- **Incorrect:** login role has broad grants → a single authorization bug could expose/modify data directly at DB layer.

#### 3.5 Validation procedure
1. **API tests (automated or manual):**
   - Call protected endpoints (e.g. donors/requests/hospitals/profile-related APIs as per app) with **no** `Authorization` header → expect 401/403 per current behavior.
   - Call with an **invalid** Bearer token → expect 401/403 (middleware sets auth error; DRF rejects).
2. **DB-side negative check (operator, sanitized):** using the API login role credentials in a controlled test session (separate from app), attempt to `SELECT` from `public.donors` (and key tables) **without** switching to `authenticated` and **without** setting the app’s claim GUCs in the same intended way—verify access is denied or returns no data as per intended least-privilege model. (Exact method depends on final role design; document the test.)
3. **Regression:** confirm authenticated flows still work (Correction 1 validation).

#### 3.6 Whether explicit administrator approval is required
**Yes** for changing role grants/privileges on hosted DB. API behavior tests can be run by QA/developers with test accounts.

---

### Correction 4 — Verify hosted migration, grant, and RLS state (mandatory)

#### 4.1 Root cause or uncertainty
- **Uncertainty:** The hosted Supabase project may not have migrations 0001–0010 applied in order, may have manual drift (extra/missing policies, altered grants, different function definitions), or may have roles/functions in unexpected states. Repo is the intended source of truth; runtime security depends on hosted match.

#### 4.2 Exact proposed correction (descriptive)
1. **Establish an approved migration inventory process** (operator): confirm which migration files have been applied (by filename/order 0001 through 0010) in the target hosted project. Use Supabase Dashboard migration history or an approved SQL inspection method performed by an administrator (**no ad-hoc destructive changes**).
2. **Verify key invariants (checklist, conceptual):**
   - 0001: `anon`, `authenticated`, `service_role` roles exist with intended characteristics contextually; schema `public` usage/grants and default privileges aligned with repo intent (as applicable).
   - 0002/0003/0006–0008: tables/indexes/constraints present as intended (including `requests.donor_id`, phone constraint form per latest corrective migrations 0007/0008 in repo—confirm hosted matches intended final state).
   - 0004: `bdr_uid`, `bdr_is_admin`, `bdr_is_hospital`, `bdr_hospital_id`, `set_updated_at`, `assign_role` exist; EXECUTE grants: helpers granted to `authenticated`/`service_role` and revoked from `PUBLIC`/`anon` as in repo; `assign_role` granted to `service_role` only and revoked from others.
   - 0005: RLS enabled on `donors`, `hospitals`, `profiles`, `requests`; broad revokes from `anon/authenticated/PUBLIC` on those tables; `authenticated` grants as in repo (`donors/hospitals/requests` table DML; `profiles` SELECT + `UPDATE (full_name)` only); policies present for the documented behaviors (admin/hospital scoping, profile self/admin rules). No unintended broad grants.
   - 0009: `bdr_uid()` and `set_updated_at()` redefined with `search_path = public, pg_temp` (and other hardening as in file).
   - 0010: `rls_auto_enable()` revoked from `PUBLIC/anon/authenticated` if function exists.
3. **If drift is found:** do **not** “fix” by weakening RLS. Produce a remediation diff plan (approved) to reconcile hosted state to repo intent (may involve running approved migrations/scripts by administrators). This plan document does not authorize changes.

#### 4.3 Files or Supabase settings affected
- **Hosted Supabase Postgres:** schema, functions, policies, grants, role attributes (inspected/changed only by approved admin actions).
- **Repo:** authoritative reference (`supabase/migrations/*`). No repo changes in this planning step.

#### 4.4 Security implications
- Missing RLS/policies/grants or wrong helper definitions can cause **data exposure or broken isolation**. Extra permissive grants/policies are dangerous. `assign_role` exposed to wrong roles is dangerous.
- Verifying state is a prerequisite for trusting any RLS-based isolation tests.

#### 4.5 Validation procedure
1. Use Supabase Dashboard **Database / Migrations** view (or equivalent admin tool) to list applied migrations; compare to 0001–0010 in order.
2. Perform **read-only** inspections (admin-only, documented procedure) of: RLS enabled flags on the four tables, presence of expected policies (by name/behavior summary), key grants on those tables, and existence/signatures of the listed functions. Record results **sanitized** (no data dumps of sensitive rows in shared notes except what is necessary and approved).
3. Optionally run the app’s RLS-focused test patterns in a **local isolated** environment that mirrors migrations (repo has `backend/authentication/tests/test_rls.py` and `DomainSchemaTestRunner`) to build confidence in policy logic—**local only**, not against hosted DB.
4. If any mismatch: open an approved remediation ticket/task before claiming safety.

#### 4.6 Whether explicit administrator approval is required
**Yes.** Any inspection beyond normal dashboard viewing that touches production data is sensitive; **any changes** to hosted schema/policies/grants require explicit admin approval and a controlled change process.

---

## Answers to the explicit questions in the request

### Q1. Required PostgreSQL login role characteristics (for the Django `DATABASE_URL` role)
**Planning answer (to be confirmed on hosted instance):**
- **LOGIN** role used only by the Django API (not shared casually).
- **Not a superuser.** (`NOSUPERUSER`.)
- **No `BYPASSRLS`.** (`NOBYPASSRLS`.)
- Able to connect to the correct database and use `public` schema as required.
- **Able to execute `SET ROLE authenticated`** in the context used by the app (see Q2). Practically this means the login role is a member of/has privilege to assume the `authenticated` role in that Postgres/Supabase setup (exact mechanism is environment-dependent; operators must verify).
- **Least privilege:** no unnecessary table/sequence/function privileges beyond what is required for the connection and for the chosen role-switch model; **do not** grant broad DML on `donors/hospitals/profiles/requests` to the login role if the security model relies on the switched `authenticated` role + RLS—this requires careful reconciliation with Django’s ORM behavior and Supabase role conventions (requires validation and approval).
- **Must not** be `service_role` and must not hold `service_role`-only powers for normal API traffic.

### Q2. Whether the login role must be a member of `authenticated` to execute `SET LOCAL ROLE authenticated`
**Planning answer:**
- In standard PostgreSQL, a role may `SET ROLE` to a role it is a **member of** (directly or indirectly) subject to privileges (`SET ROLE` privilege model). The application does `SET LOCAL ROLE authenticated` (`backend/authentication/middleware.py`). Therefore, **in the typical PostgreSQL model, the login role must have the right to assume the `authenticated` role**—most commonly by being granted membership in `authenticated` (or having appropriate role privileges). Whether Supabase imposes additional constraints depends on configuration, but the operational expectation is: the API login role must be allowed to switch into the `authenticated` role context used by RLS policies.
- **Uncertainty (hosted):** The exact grant/membership needed in the target Supabase project must be verified by an administrator (e.g. confirm the login role is a member of `authenticated` or has equivalent `SET ROLE` permission). **This is a required verification step**, not something assumed from repo alone.
- **Do not** grant `SET ROLE` broadly inappropriately; grant only as needed for this login role.

### Q3. Whether the role has superuser or `BYPASSRLS` privileges
**Planning answer:** **It must not.** Any superuser or `BYPASSRLS` attribute on the `DATABASE_URL` role **defeats RLS** and is unacceptable for this design. Verification is mandatory (admin check of role attributes). If found, treat as a **critical remediation** (Correction 1).

### Q4. Whether the role has only the minimum necessary database privileges
**Planning answer (target state):**
- Minimum necessary means: ability to establish connections to the intended DB, use required schema(s), perform the role switch to `authenticated` as designed, and allow the application’s ORM/queries to function **under the enforced `authenticated` + RLS context** without granting the login role standing privileges to bypass tenant isolation.
- Because repo migrations grant specific privileges to the `authenticated` role (0005), a clean model is often: login role can `SET ROLE authenticated` and the effective permissions come from `authenticated` + RLS. However, practical Django/Postgres behavior (and any direct SQL, extensions, sequence usage patterns) may require the login role to have certain USAGE/EXECUTE/sequence privileges in addition. **This requires empirical validation** in the deployed environment with the actual query set. The plan is to:
  1. Start from a restrictive posture (no superuser, no `BYPASSRLS`, no broad table DML on domain tables for the login role if feasible), 
  2. Test authenticated app flows end-to-end,
  3. Grant **only the minimal additional privileges** that are demonstrably required and do not weaken isolation (document each grant with justification).
- **Uncertainty:** Exact minimal grant set is **NOT VERIFIED** here; must be discovered via controlled testing and approved.

### Q5. Supabase connection method and pooler compatibility with transaction-local `SET ROLE` and JWT claim settings
**Planning answer:** See **Correction 2** in detail. In summary:
- Identify direct vs pooler and pooler mode from deployment config/settings (operator). Repo gives no hint.
- The app sets **transaction-local** GUCs (`set_config(..., true)`) and does **`SET LOCAL ROLE authenticated`** inside `transaction.atomic()` per request. This is most naturally compatible with semantics where these apply within the transaction on the server connection handling that work. **Transaction pooling** can be risky if role/GUC state is mishandled across transactions or if the pooler restricts role changes; **session pooling** is often safer for session/role state but still requires validation; **direct connections** avoid pooler quirks but have operational limits. **No definitive “safe” choice is stated in repo**—operators must validate with isolation and leakage tests (§7–§8). If incompatible, do **not** disable RLS or use bypassing roles; pursue approved architectural alternatives.

### Q6. Whether unauthenticated requests remain safely restricted
**Planning answer:** See **Correction 3**. Application layer (DRF permissions, `IsAuthenticatedUser`/role classes) is the primary gate: unauthenticated requests should receive 401/403 for protected APIs. The DB layer is **not** automatically safe for unauthenticated paths because middleware does not set `authenticated` RLS context and the login role is used—therefore **login role must be minimally privileged and non-bypassing**. Validation requires: API negative tests + a controlled DB-level check that the login role cannot read/write sensitive domain tables without the app’s authenticated context/model (as designed). Any discovery of data exposure via unauthenticated code paths is a **blocker** until fixed (likely code + role changes, both needing approval).

### Q7. How to verify RLS isolation between two different hospital accounts and an administrator
**Planning answer (validation procedure, no SQL executed here):**
Perform in a **staging/demo environment** with **test/demo data only** (no real sensitive data), using approved test accounts/profiles provisioned via the normal trusted process (e.g. `assign_role`/admin tooling as per project operations—do **not** describe secret procedures in shared logs):

1. **Prepare identities (operator, approved):**
   - Create or identify **Hospital A** user/profile linked to Hospital A (`profiles.role='hospital'`, correct `hospital_id`).
   - Create or identify **Hospital B** user/profile linked to Hospital B (different `hospital_id`).
   - Create or identify an **Admin** user/profile (`role='admin'`).
   Ensure all have valid Supabase Auth credentials for sign-in in the frontend/demo flow (or obtain valid JWTs through approved test means) **without exposing secrets in this plan**.

2. **Test A — Hospital A cannot see Hospital B’s requests (and vice versa):**
   - Sign in as **Hospital A** (frontend) and call the requests listing/API endpoints the app exposes for hospital users. Record (sanitized): that only Hospital A–scoped requests appear (or none from Hospital B). 
   - Repeat as **Hospital B**: confirm no Hospital A–scoped requests appear in results.
   - **Expected:** strict scoping to the authenticated hospital’s `hospital_id` per app behavior and RLS policy intent (`requests` scoped by `hospital_id = bdr_hospital_id()` or admin). Any Hospital B request visible to Hospital A (or vice versa) is a **FAIL/blocker**.

3. **Test B — Hospital A cannot access Hospital B’s hospital record context inappropriately:**
   - As **Hospital A**, attempt to access/list hospital resources in ways the UI/API allows; verify responses are limited to Hospital A’s context (per `hospitals` RLS: hospital sees own row via `bdr_hospital_id()`/policy intent). Attempting to access another hospital’s ID via crafted requests should be rejected or return nothing as designed.
   - **Expected:** no cross-hospital hospital record leakage.

4. **Test C — Donors visibility (per 0005 intent):** SELECT on donors allowed to `authenticated` if admin OR hospital (policy states “allowed if bdr_is_admin() OR bdr_is_hospital()”). Therefore hospitals may be allowed to read donors in the current model—this is **by design in repo**, not a leak between hospitals. Verify behavior matches documented intent: hospitals can list/search donors as allowed; admins can manage donors per permissions. Do **not** mislabel this as isolation failure unless policy intent differs from product intent (product intent is in repo/docs; this test confirms consistency).

5. **Test D — Profiles isolation:**
   - As **Hospital A**, fetch own profile; verify cannot read Hospital B’s profile (and cannot read admin profile details beyond what policies allow). 
   - As **Admin**, verify admin can read profiles per policy (`id = bdr_uid() OR bdr_is_admin()`) as intended.
   - Attempt to update profile fields beyond `full_name` for a hospital user via API—expect rejection (app permissions + RLS/grant limits `UPDATE (full_name)` on `profiles`).

6. **Test E — Admin full access (within app rules):**
   - As **Admin**, verify access to admin-listed donors/hospitals/requests as permitted by the application (and consistent with RLS allowing admin). Confirm admin actions (create/update/delete donors per app rules, etc.) work as designed.

7. **Evidence recording (sanitized):** For each test record pass/fail, timestamps conceptually, and **no tokens, no passwords, no full JWTs, no real PII** in notes. Screenshots should be redacted.

**If any cross-tenant read/write occurs outside intended admin/hospital scope:** mark as **CRITICAL**, stop deployment/demo expansion, and require remediation (role/RLS/migration/context investigation) with approval before proceeding.

### Q8. How to validate that database session identity cannot leak between requests
**Planning answer (validation procedure):**
This tests whether a previous request’s transaction-local role/GUC state affects a later request under pooling/connection reuse.

1. **Controlled interleaving (manual, two identities):**
   - Send Request 1 as **Hospital A** (valid JWT) → receive Hospital A–scoped response (e.g. list of A’s requests).
   - Immediately send Request 2 as **Hospital B** (valid JWT) → receive Hospital B–scoped response only.
   - Immediately send Request 3 again as **Hospital A** → verify results still correspond to Hospital A (not contaminated by Hospital B context).
   - Repeat in varied order (A,B,A,B, admin,B, A…) with short delays.
2. **Automated script approach (operator-written, run locally against deployed demo with test accounts only):** loop through authenticated calls alternating users and assert response scoping invariants (e.g. all returned request `hospital_id` values match the expected hospital for that token). **Do not** log tokens or sensitive payloads in shared outputs; log only pass/fail and IDs/categories.
3. **Edge cases:**
   - Requests with **no token** followed by authenticated requests: ensure no privilege bleed (no access granted incorrectly).
   - Rapid concurrent requests (light load) to increase chance of pooler reuse issues; observe for anomalies.
4. **Pooler-specific note:** If using **session pooling**, leakage risk is higher in theory if locals are not reset—but the app sets `SET LOCAL ROLE` and `set_config(..., true)` which are transaction-local; middleware wraps each request in `transaction.atomic()`, so locals should be scoped to that transaction. Still, validate empirically. If using **transaction pooling**, each transaction is often isolated on the server side, but behavior varies—validate empirically.
5. **Failure indicators:** any response containing data belonging to the wrong hospital/admin scope for the presented token, or any unexpected 500/role errors correlated with pooling. On failure: **stop**, treat as **blocker**, investigate pooler mode and middleware/transaction flow (requires approval for any code/config changes).

### Q9. Hosted migration, grant, and RLS verification requirements
**Planning answer:** See **Correction 4** above. Minimum requirements before claiming DB/RLS safety for Render demo:
- Confirm applied migrations are **exactly 0001–0010 in order** (or an approved superseding set documented) on the hosted Supabase project.
- Confirm RLS **enabled** on `donors`, `hospitals`, `profiles`, `requests`.
- Confirm policies exist matching repo 0005 intent (admin/hospital/profile rules) with no unintended permissive overrides.
- Confirm grants: broad revokes on those tables from `anon/authenticated/PUBLIC` as intended; `authenticated` has only the grants listed in 0005; `profiles` UPDATE limited to `full_name` column grant in effect.
- Confirm helper functions `bdr_uid/bdr_is_admin/bdr_is_hospital/bdr_hospital_id/set_updated_at/assign_role` present with correct `search_path`/security attributes per 0004/0009 and EXECUTE grants as specified (helpers to `authenticated`/`service_role`, `assign_role` to `service_role` only).
- Confirm `rls_auto_enable` revoked from client roles if present (0010).
- Confirm `DATABASE_URL` login role attributes (Q1–Q3) and membership for `SET ROLE authenticated` (Q2).
- Record all findings in a **sanitized internal verification log** (no secrets/data dumps) and obtain admin sign-off before proceeding to public demo.

---

## Recommended implementation order (planning only)

Execute in this order to minimize risk and to validate dependencies:

1. **P1 — Freeze and document current state (no changes):** operator records current `DATABASE_URL` connection type/pooler mode (sanitized), current Render env var names present (not values), and current Supabase project identity confirmation (separately). Obtain **approval to proceed** with remediation work.
2. **P2 — Hosted migration/grant/RLS verification (read-only inspection by admin):** complete Correction 4 checklist. If any drift found, **stop** and create an approved reconciliation plan (do not proceed to role changes blindly).
3. **P3 — Define target role model and approve it:** decide the login role attributes and privilege model (Correction 1/Q1–Q4), including whether/how the login role assumes `authenticated` (Q2). Get **explicit admin + security/owner approval** on the model.
4. **P4 — Apply role/privilege changes in hosted DB (approved):** implement Correction 1 under change control. Update `DATABASE_URL` in Render (secret) to the corrected role/connection string. **Do not** change code yet.
5. **P5 — Verify connection/pooler compatibility (Correction 2):** confirm topology, run functional smoke and RLS isolation + leakage tests (§7–§8) against deployed backend. If incompatible, escalate for approved topology/design change (do not weaken RLS).
6. **P6 — Validate unauthenticated safety (Correction 3):** API negative tests + DB-level least-privilege checks as applicable.
7. **P7 — Full end-to-end demo smoke:** sign-in, CORS, role scoping, admin flows, no secret leakage in client. Align with D-03B/D-03E checklists.
8. **P8 — Final sign-off:** document results (sanitized), confirm “SAFE ONLY AFTER SPECIFIC CORRECTIONS” items from D-03D are satisfied, then proceed to demo (or remain blocked if any step fails).

**Note:** Steps involving hosted DB/Render/Supabase changes must be done by authorized personnel; this plan does not perform them.

---

## List of approvals needed (before any implementation)

1. **Project owner/admin approval** to perform hosted Supabase/Postgres inspections and any role/grant/migration reconciliation changes (with change window if required).
2. **Explicit approval of the target API login role design** (attributes: no superuser, no `BYPASSRLS`, allowed to assume `authenticated` context, least-privilege grant matrix) — Correction 1 / Q1–Q4.
3. **Approval to change `DATABASE_URL` in Render** to the corrected role/connection string (and to rotate credentials if done as part of remediation).
4. **Approval of Supabase connection/pooler configuration changes** (if any) and acceptance of validated pooler mode — Correction 2.
5. **Approval for any code or migration changes** if validation reveals the current middleware model (`SET LOCAL ROLE authenticated` + GUCs) is incompatible with the required security posture under chosen pooling (this plan assumes **no code/migration changes**; any change requires separate design review).
6. **Approval to run controlled RLS/isolation and leakage tests** against the demo/staging environment using test accounts (ensuring no production sensitive data is involved).
7. **Final go/no-go approval** to proceed with Render/Vercel demo deployment after all validation steps pass and documentation is complete.

---

## What this plan does NOT do (reminder)

- Does not connect to any database.
- Does not execute SQL.
- Does not modify code, migrations, environment variables, settings, or hosted infrastructure.
- Does not deploy.
- Does not commit or push.
- Does not print secrets.