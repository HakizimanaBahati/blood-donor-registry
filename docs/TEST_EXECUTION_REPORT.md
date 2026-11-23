# Blood Donor Registry — Test Execution and Acceptance Report

**Plan:** Software Testing and Acceptance Plan, 23 November 2026  
**Execution date:** 23 November 2026  
**Environment:** local development only — isolated PostgreSQL 18 cluster on `127.0.0.1:55432`, Django 6.1.3 REST API, Next.js 16.4.6 frontend, offline dev-login tokens.  
**Remote Supabase:** no migrations, schema changes or data writes were applied to any hosted project.

---

## 1. Executive summary

All executed functional, authorization, isolation, eligibility, analytics and RLS checks passed on the isolated local environment. The application met the local acceptance criteria for authentication, role separation, donor/request workflows and the 90-day rule.

Production acceptance remains **pending** because the real Supabase Auth password flow, live JWKS/asymmetric verification, hosted email/recovery redirects and deployed configuration cannot be validated without hosted project credentials. One test case (`AUTH-03`) is therefore blocked.

| Metric | Result |
|---|---|
| Backend automated tests | 97 passed, 0 failed |
| Frontend automated tests | 27 passed, 0 failed |
| Runtime API checks (isolated DB) | 58 passed, 0 failed |
| SQL assertion suites | 2 passed, 0 failed |
| Frontend route smoke checks | 8 passed, 0 failed |
| Static checks (lint, typecheck, build) | 3 passed, 0 failed |
| **Total executed checks** | **195 passed, 0 failed** |
| Blocked test cases / groups | `AUTH-03`; production-readiness validation |
| Non-functional objectives not exercised | performance, induced-error reliability, usability, browser compatibility, responsiveness |

---

## 2. Environment and safety controls

| Control | Evidence |
|---|---|
| Local database started with `.\scripts\local-db.ps1 start` | `Local PostgreSQL listening on 127.0.0.1:55432` |
| Local migrations + seed + assertions with `.\scripts\apply-local-migrations.ps1` | `ALL DATABASE ASSERTIONS PASSED`, `LOCAL DATABASE READY` |
| Django tests use the custom runner and `TEST_DATABASE_URL` | `Ran 97 tests ... OK`; test runner switches to the isolated local cluster |
| Runtime API tests explicitly set `DATABASE_URL=postgresql://postgres@127.0.0.1:55432/blood_registry` | 58/58 checks passed |
| Temporary test records | one `[TEST] ACCEPTANCE Donor` and one `[TEST] acceptance` request created and deleted; final counts remained `donors=12`, `requests=6`, leftovers `0/0` |
| Direct RLS checks | run inside a transaction that was rolled back; all assertions passed |
| Test artifacts | the runtime smoke script and RLS SQL file were temporary files in the approved temp directory and are not committed to the repository |

### Environment finding during execution

`backend/.env` currently sets `DATABASE_URL` to a hosted Supabase pooler. An initial exploratory smoke run therefore hit that hosted database; every authenticated request returned `403` because the offline demo identities do not exist there. No migration was run against it, no record was created or modified there, and the final results were produced only after overriding `DATABASE_URL` to the isolated local database.

This is a **test-process hazard**, not an application defect: local testing must always override `DATABASE_URL` or temporarily rely on `TEST_DATABASE_URL` as documented in the README.

---

## 3. Verification commands and results

| Area | Command / action | Result |
|---|---|---|
| Database schema, seed, RLS | `.\scripts\apply-local-migrations.ps1` | `ALL DATABASE ASSERTIONS PASSED` |
| Backend | `Push-Location backend; & "..\.venv\Scripts\python.exe" manage.py test --verbosity 1 --noinput; Pop-Location` | `Ran 97 tests ... OK` |
| Frontend unit tests | `npm test` | 6 files, 27 tests passed |
| Frontend types | `npm run typecheck` | no errors |
| Frontend lint | `npm run lint` | no errors |
| Frontend production build | `npm run build` | compiled successfully; 15 routes generated |
| Backend startup | `GET /health` on an isolated port | `{"status":"ok"}` |
| Frontend startup | `next dev -p 3001`, `GET /login` | HTTP 200 |
| Route smoke | `/login`, `/admin/dashboard`, `/hospital/dashboard`, `/analytics`, `/donors`, `/requests`, `/hospitals`, `/profile` | all HTTP 200 |
| Runtime API matrix | local smoke script against `127.0.0.1:8003` with local `DATABASE_URL` | 58/58 PASS |
| Direct RLS matrix | `psql -f bdr_rls_acceptance.sql` against isolated DB | `ALL DIRECT RLS CHECKS PASSED` |
| Log hygiene | scan of the 182-line Django server log for JWTs, bearer tokens, passwords, API keys and secret assignments | no matches |

---

## 4. Detailed test ID results

### A. Authentication

| ID | Status | Evidence |
|---|---|---|
| AUTH-01 | PASS | Admin dev-login returned 200 and `/api/auth/me/` resolved role `admin`. Caveat: offline demo login, not real Supabase password login. |
| AUTH-02 | PASS | Hospital dev-login returned 200 and `/api/auth/me/` resolved role `hospital` with the correct `hospital_id`. Same caveat. |
| AUTH-03 | BLOCKED | Real Supabase password rejection cannot be exercised without hosted credentials. Only the offline invalid-account case was checked (400). |
| AUTH-04 | PASS | `GET /api/donors/` without a token returned 401. |
| AUTH-05 | PASS | Invalid token returned 401; expired, wrong-audience, wrong-issuer, tampered, unsigned and unsupported-algorithm tokens are covered by the Django auth tests. |
| AUTH-06 | PASS | `GET /api/auth/me/` returned the server-resolved profile for admin and hospital tokens. |
| AUTH-07 | PASS | Frontend Vitest: sign-out clears profile; missing session sends no authenticated request. Backend `POST /api/auth/logout/` returned 200 with the stateless-session explanation. |

### B. Admin authorization

| ID | Status | Evidence |
|---|---|---|
| ADM-01 | PASS | `/admin/dashboard` returned HTTP 200; static generation passed. |
| ADM-02 | PASS | Admin donor list 200; analytics totals reconciled with the same donor records. |
| ADM-03 | PASS | Admin created `[TEST] ACCEPTANCE Donor` → 201, then deleted it. |
| ADM-04 | PASS | Admin PATCH of the temporary donor → 200. |
| ADM-05 | PASS | Admin hospital list 200; Django tests cover admin create/update. |
| ADM-06 | PASS | Admin request list spanned all three hospitals (6 seed records). |
| ADM-07 | PASS | Admin analytics summary and blood-type chart endpoints returned 200. |

### C. Hospital authorization

| ID | Status | Evidence |
|---|---|---|
| HOS-01 | PASS | `/hospital/dashboard` returned HTTP 200. |
| HOS-02 | PASS | Hospital One could read its own hospital detail (200). |
| HOS-03 | PASS | Hospital donor list returned 12 authorized donor records. |
| HOS-04 | PASS | Hospital created a blood request → 201. |
| HOS-05 | PASS | Hospital request list contained only `hospital_id=11111111-...`. |
| HOS-06 | PASS | Hospital One reading Hospital Two's request returned 404. |
| HOS-07 | PASS | Hospital list/create/update returned 403; other hospital detail returned 404. |
| HOS-08 | PASS | Hospital donor create and hospital create returned 403. |
| HOS-09 | PASS | Profile role PATCH returned 405; direct SQL role change failed with `insufficient_privilege`; role is excluded from write serializers. |
| HOS-10 | PASS | Assigning a request to another hospital was blocked (400 after RLS hid the foreign hospital; API permission tests also expect 403). Changing an existing request's hospital was likewise blocked. |

### D. Donor management

| ID | Status | Evidence |
|---|---|---|
| DON-01 | PASS | Admin donor create 201 with server-generated eligibility fields. |
| DON-02 | PASS | Admin donor detail 200; hospital detail returns authorized fields with phone redacted when ineligible. |
| DON-03 | PASS | Admin donor PATCH 200. |
| DON-04 | PASS | `?search=ACCEPTANCE` returned the created test donor. |
| DON-05 | PASS | `?blood_type=O+` returned only O+ records; invalid type returned 400. |
| DON-06 | PASS | `?eligible=true` returned only records with `eligible=true`. |
| DON-07 | PASS | Invalid blood type, invalid phone, duplicate phone, future date and missing required fields are rejected (runtime 400 + Django validation tests). |
| DON-08 | PASS | Hospital donor create returned 403. |

### E. Blood requests

| ID | Status | Evidence |
|---|---|---|
| REQ-01 | PASS | Hospital request create 201. |
| REQ-02 | PASS | Missing required fields returned 400. |
| REQ-03 | PASS | Invalid blood type returned 400. |
| REQ-04 | PASS | Eligible donor assignment succeeded and was reflected in the response. |
| REQ-05 | PASS | Ineligible donor assignment returned 400 with `error.code = ineligible_donor` and `days_until_eligible`. |
| REQ-06 | PASS | Hospital request history returned its own 4 requests (3 seed + 1 temporary). |
| REQ-07 | PASS | Hospital changed its own request status to `fulfilled` → 200. |
| REQ-08 | PASS | Hospital PATCH of another hospital's request returned 404. |
| REQ-09 | PASS | Hospital GET of another hospital's request returned 404. |

### F. 90-day eligibility

| ID | Status | Evidence |
|---|---|---|
| ELI-01 | PASS | No recent donation is eligible; eligible filter returned 8 records, all with `eligible=true`. |
| ELI-02 | PASS | 30 days ago → `eligible=false`, `days_until_eligible=60`. |
| ELI-03 | PASS | 89 days ago → `eligible=false`, `days_until_eligible=1`. |
| ELI-04 | PASS | Exactly 90 days ago → `eligible=true`, `days_until_eligible=0`. |
| ELI-05 | PASS | Missing history → `eligible=true`, `eligibility_badge=no_history` (preliminary screening only). |
| ELI-06 | PASS | API rejected an ineligible donor assignment with `ineligible_donor`. |

Clinical screening remains outside the scope of this software rule.

### G. Data security and RLS

| ID | Status | Evidence |
|---|---|---|
| SEC-01 | PASS | Unauthenticated API request 401; anonymous SQL role saw 0 donors and 0 requests. |
| SEC-02 | PASS | Hospital read/updated its own request (API 200; direct RLS UPDATE changed 1 row). |
| SEC-03 | PASS | Hospital read of another hospital's request: API 404 and direct SQL returned 0 rows. |
| SEC-04 | PASS | Hospital UPDATE of another hospital's request: API 404 and direct SQL changed 0 rows. |
| SEC-05 | PASS | Direct SQL role escalation failed (`insufficient_privilege`); profile API rejects the action. |
| SEC-06 | PASS | Admin read all 6 requests across three hospitals. |
| SEC-07 | PASS | RLS remains enabled; `anon` has no table grants; unauthorized SQL operations were denied; no RLS bypass or privilege grant was used to pass a test. |
| SEC-08 | PASS | Invalid JWT returned 401; Django tests cover malformed, expired, wrong-audience, wrong-issuer, tampered and unsigned tokens. |
| SEC-09 | PASS | Server-log scan found no JWTs, bearer tokens, passwords, `sb_secret_` keys or secret assignments; auth logging redaction is unit-tested. |
| SEC-10 | PASS | Ineligible donor phone was `null` for hospital staff; admin still sees it. |

### H. Dashboard and analytics

| ID | Status | Evidence |
|---|---|---|
| ANA-01 | PASS | Admin dashboard route 200; admin summary endpoint 200. |
| ANA-02 | PASS | Hospital dashboard route 200; hospital summary endpoint 200. |
| ANA-03 | PASS | `total_donors` 13 matched 13 authorized records at the same snapshot. |
| ANA-04 | PASS | `eligible_donors` 8 matched 8 records with `eligible=true`. |
| ANA-05 | PASS | `ineligible_donors` 5 matched total minus eligible. |
| ANA-06 | PASS | Admin `total_requests` 7 matched the 7-row admin list. |
| ANA-07 | PASS | Chart returned all eight blood types with counts matching filtered donor queries. |
| ANA-08 | PASS | Recent requests returned at most 5 authorized records. |
| ANA-09 | PASS | Hospital One `total_requests` 4 matched its 4 visible requests. |

Counts above include the one temporary test donor/request; both were deleted afterwards and the database returned to 12 donors / 6 requests.

### I. Non-functional objectives

| Category | Status | Evidence / gap |
|---|---|---|
| Performance | NOT TESTED | No load or latency benchmark was performed. |
| Reliability | NOT TESTED | No induced server-error/failure-injection scenario was executed. |
| Security | PASS | Authentication, RBAC and RLS were exercised together. |
| Usability | NOT TESTED | No manual browser walkthrough of forms and navigation was recorded. |
| Validation | PASS | Invalid donors, requests, blood types and missing fields returned clear 400 envelopes. |
| Compatibility | NOT TESTED | Tests ran in jsdom/Node, not across supported browsers. |
| Responsiveness | NOT TESTED | No desktop/tablet/mobile viewport testing was performed. |
| Recovery | PASS | Auth Vitest tests cover sign-out, missing session and token refresh; dev-login tokens were obtained repeatedly in separate sessions. Full browser re-login was not automated. |

---

## 5. Updated results register (plan section 8)

| Test group | Status |
|---|---|
| Backend startup | PASS |
| Admin authentication | PASS |
| Hospital authentication | PASS |
| Admin dashboard | PASS |
| Hospital dashboard | PASS |
| Admin authorization | PASS |
| Hospital authorization | PASS |
| Cross-hospital isolation | PASS |
| Donor workflows | PASS |
| Request workflows | PASS |
| 90-day eligibility boundary | PASS |
| RLS security testing | PASS |
| Production readiness | BLOCKED |

---

## 6. Defects, risks and decisions

**Application defects identified:** none in the executed scope.  
**Application defects resolved:** not applicable.

**Process findings / outstanding risks**

1. `backend/.env` points at a hosted Supabase project. Local test runs must override `DATABASE_URL`; the initial accidental connection was read-only in effect (all authenticated requests were denied) and no remote migration or write occurred.
2. Real Supabase Auth login with a password (`AUTH-03`), live JWKS/RS256 verification, password-recovery email redirects and hosted RLS with the restricted `bdr_api` role were not exercised.
3. The development login endpoint is enabled by `DJANGO_DEBUG=true`. Production must keep `DEBUG=false`; the settings tests confirm missing production secrets/DB URL fail fast.
4. `.gitignore` excludes `.env`, `.env.*` (except `.env.example`), keys and local database files; no credential is committed.
5. Pre-existing dev servers occupied ports 8000/3000; final runtime checks used isolated ports to avoid stale code or stale database connections.

---

## 7. Final testing report (plan section 10)

- **Tests executed:** 195 automated/runtime checks (97 backend, 27 frontend, 58 API, 2 SQL suites, 8 routes, 3 static checks).
- **Passed:** 195.
- **Failed:** 0.
- **Blocked:** `AUTH-03` plus hosted production-readiness validation.
- **Not tested:** five non-functional objectives listed in section 4.I.
- **Defects identified:** 0.
- **Defects resolved:** 0.
- **Outstanding security risks:** hosted Auth/JWKS/recovery validation; ensure `DEBUG=false` and dev-login disabled in production; use a restricted database role rather than a superuser for the deployed API.

### Final acceptance decision

**Local acceptance: PASS.** All local functional, authorization, isolation, eligibility and RLS evidence is green.

**Production acceptance: PENDING / BLOCKED.** Final production acceptance requires validation against a real Supabase project with real Auth users, live JWT verification, configured recovery redirects and reviewed deployment secrets. No critical functional or security defect was found in the locally executed scope.
