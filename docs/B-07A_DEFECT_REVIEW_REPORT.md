# B-07A — Defect Review and Security Regression Planning Report

Date: 2026-11-23
Review type: read-only inspection and planning
Primary evidence: `docs/B-06B_E2E_TEST_REPORT.md`, backend implementation and automated tests, frontend implementation and test tooling, Supabase migrations and RLS policies, prior engineering decisions.

## 1. Executive summary

All 67 B-06B results were reviewed. B-06B executed 62 PASS assertions, produced 0 FAIL assertions, recorded 4 BLOCKED frontend workflow tests, and left 1 authorization item NOT TESTED. No executed assertion failed.

This review confirms **one defect**: oversized request notes are not rejected by the API serializer and reach the database constraint, producing a generic `500/internal_error` instead of a field-level `400/validation_error`. Severity is **Medium**: the behavior is user-visible and incorrect, but the database constraint still prevents invalid persistence and the error envelope does not leak SQL text, stack traces, credentials, or other sensitive data.

No Critical or High findings were identified. Authentication, role resolution, hospital request isolation, donor phone redaction, JWT claim validation, RLS policies, and generic error handling were verified as effective within the reviewed scope. Most other B-06B observations are unresolved **product decisions**, not defects. The blocked frontend workflows and the unexecuted A10 scenario are **testing limitations** with low residual security impact because API-side controls are covered separately.

No fixes were implemented. No application code, tests, configuration, environment files, database contents, migrations, or RLS policies were changed.

### Review coverage of all 67 B-06B results

| Phase | Results reviewed | Disposition |
|---|---:|---|
| Phase 1 — Safety preconditions | 5 PASS | Environment isolation and baseline counts accepted as recorded. |
| Phase A — Authentication and roles | 9 PASS, 1 NOT TESTED | A1–A9 support the verified security conclusion; A10 is not executable as defined. |
| Phase B — Donor management | 10 PASS | Donor CRUD, validation, not-found, deletion, and non-leaking errors accepted. |
| Phase C — Donor eligibility | 8 PASS | 90-day boundaries, filtering, and phone redaction accepted. |
| Phase D — Blood requests | 16 PASS | Core request workflow accepted; D4, D11, D13, D14, D16 remain product decisions. |
| Phase E — Data integrity and isolation | 11 PASS | E10 confirms BUG-1; E1–E9 and E11 support isolation, constraints, and error-envelope conclusions. |
| Phase F — Frontend | 1 PASS, 4 BLOCKED | F0 accepted; F1–F4 remain blocked by the absence of an approved browser driver. |
| Cleanup verification | 2 PASS | Baseline restoration accepted as recorded. |
| **Total** | **62 PASS, 0 FAIL, 4 BLOCKED, 1 NOT TESTED** | **All 67 results reviewed.** |

## 2. Confirmed defects

### DR-01 — Oversized request notes produce `500/internal_error`

| Attribute | Assessment |
|---|---|
| Classification | **Medium** — confirmed defect |
| B-06B evidence | E10: request notes longer than the database limit returned `500/internal_error` with `details: null`; no stack trace, SQL text, or secret was exposed. Section 4 records this as BUG-1. |
| Static evidence | `supabase/migrations/0002_tables.sql` defines `requests_notes_length` as `notes IS NULL OR length(notes) <= 1000`. `backend/requests_app/serializers.py::BloodRequestSerializer` declares `notes` as optional text with blank/null allowed, but no maximum-length validator. `backend/requests_app/models.py::BloodRequest.notes` is an unbounded `TextField` projection. |
| Root cause | Validation responsibility is split: the database enforces a 1000-character CHECK constraint, but the API does not enforce the same limit before insert/update. The resulting database error is unhandled at the serializer layer and is converted by `backend/common/errors.py::api_exception_handler` into a generic 500. |
| Impact | A client can turn ordinary invalid input into a server error. This degrades UX, creates noisy exception logs, and makes API contracts inconsistent with donor name validation, which already returns `400/validation_error`. No data-integrity or information-disclosure impact was observed. |
| Why not Critical/High | The write is rejected by the database, the response is generic, hospital scoping and authentication are unaffected, and no sensitive data is returned. |
| Verified vs assumed | Verified: B-06B E10 result and current serializer/model/migration source. Assumed: the product intends notes to be capped at 1000 characters; this must be approved as decision #2 before implementation. |

## 3. Security review findings

The review found no authentication or authorization bypass, no cross-hospital data exposure, and no sensitive-value leakage in the reviewed paths. The following controls were verified:

| Control | Evidence | Result |
|---|---|---|
| JWT verification | `backend/authentication/jwt.py::verify_access_token` restricts algorithms, requires `exp`/`sub`/`iat`, verifies signature, expiry, audience, issuer, and UUID subject; asymmetric keys are resolved through cached JWKS. `backend/authentication/tests/test_auth.py` covers negative token cases. | No finding. |
| Role resolution | `backend/authentication/services.py::get_app_user` resolves `admin`/`hospital` from `public.profiles` using the verified subject. JWT `role` claims and request-body `role` fields are not trusted. A3–A6 and BREAK-IT attempt 3 support this. | No finding. |
| Default access control | `backend/config/settings.py` sets `IsAuthenticatedUser` as the default DRF permission and `SupabaseJWTAuthentication` as the default authenticator. A1/A2 passed. | No finding. |
| Admin-only write paths | Donor create/update/delete and hospital list/create/update use `IsAdminUser`. A7–A9, B1–B9, and `backend/donors/tests/test_api.py` support this. | No finding. |
| Hospital request isolation | `backend/requests_app/views.py::ScopedRequestQuerysetMixin` filters non-admin queries by `hospital_id`; `BloodRequestSerializer._assert_hospital_allowed` blocks cross-hospital writes; RLS policies in `0005_rls.sql` provide a second layer. E1–E4 and E7 passed. | No finding. |
| Donor phone visibility | `backend/donors/serializers.py::DonorSerializer.to_representation` sets `phone` to null for non-admin users when the donor fails the registry screen. C8 passed. | No finding. |
| Database constraints | `0002_tables.sql` enforces blood type, units, status, notes length, non-blank names, profile role consistency, and donor phone format. E5, E8, E9 passed. | No finding beyond DR-01 validation gap. |
| RLS and grants | `0005_rls.sql` revokes anonymous access, grants authenticated DML only on domain tables, limits profile updates to `full_name`, and scopes request policies to admin or own hospital. `0009`/`0010` harden helper search paths and revoke a Supabase dashboard helper. | No finding. |
| Claims propagation | `backend/authentication/middleware.py` verifies the bearer token transaction-locally and sets RLS claim GUCs/role for authenticated requests. `test_middleware.py` covers emitted statements and local database role activation. | No finding. |
| Error exposure | `backend/common/errors.py` returns coded envelopes and a generic 500 with `details: null` for unhandled exceptions. JWT failure logs are sanitized and production auth logging is suppressed to warning level. B10, E10, E11 passed. | No finding. |
| Debug-only login | `backend/authentication/dev_login.py` is gated by `DJANGO_DEBUG=true` and is not a production authentication mechanism. P4 passed under local-only conditions. | No finding. |
| Ineligible-donor error details | D10 and `ensure_donor_selectable()` include a donor identifier in the `ineligible_donor` error body. | **Low hardening observation**, not a confirmed defect. The identifier is not a credential, but it is unnecessary for the client message and may be removed if product approves. Do not remove `days_until_eligible` or the eligibility badge. |
| Unused hospital permission | `IsHospitalUser` is defined only in `backend/authentication/permissions.py`; no endpoint references it. A10 has no defined scenario or API surface. | **Low hardening observation / testing limitation**, not a confirmed defect. Current hospital behavior is enforced through profile roles, scoped querysets, and RLS. |

No recommendation in this report removes or relaxes JWT verification, admin checks, hospital ownership checks, phone redaction, RLS policies, or database constraints.

## 4. Product decisions requiring approval

These are observed behaviors, not test failures. They must be converted into explicit requirements before being asserted as PASS/FAIL.

### 4.1 Request status transitions

- **Observed (B-06B D12, D13, D14):** `pending → fulfilled`, `fulfilled → pending`, and direct creation as `fulfilled` are accepted. No state machine is enforced.
- **Implications:** Fulfillment auditability is weak; accidental reversal is possible; analytics can be distorted; client behavior depends on undocumented conventions.
- **Recommended resolution:** Approve an explicit state machine, such as creation limited to `pending`, `pending → fulfilled|cancelled`, and any reversal restricted to a named role with an audit reason. If current behavior is intended, document it as the requirement.
- **Implementation status:** Not implemented.

### 4.2 Notes and name length validation

- **Observed (B-06B E10, B10):** Oversized notes produce `500/internal_error`; oversized donor names produce `400/validation_error` with a `name` field.
- **Implications:** Inconsistent API contract, avoidable 500s, and frontend cannot rely on uniform validation feedback.
- **Recommended resolution:** Approve 1000 characters for request notes and 200 characters for donor names as the public contract. Enforce both at the API boundary, keep the database CHECK constraints as defense in depth, and mirror limits in the frontend form.
- **Implementation status:** Not implemented; DR-01 depends on this approval.

### 4.3 Blood-type compatibility

- **Observed (B-06B D11):** A request can link a donor whose blood type differs from the request type; API returned `201`.
- **Implications:** Potential clinical/data-quality concern and user confusion. The existing 90-day screen is clearly labelled as preliminary, but blood-type compatibility has no documented rule.
- **Recommended resolution:** Decide whether mismatch is (a) allowed with a warning, (b) blocked by a hard validation rule, or (c) permitted only with an explicit override and audit trail. If blocked, define the compatibility matrix server-side and keep it independent of client UI.
- **Implementation status:** Not implemented.

### 4.4 Cross-hospital request creation status codes

- **Observed (B-06B D4, D15):** A hospital attempting to create or modify a request for another hospital receives `400/validation_error` on `hospital_id`, not `403/permission_denied`. The other hospital is outside the RLS-scoped `Hospital` queryset, so serializer field validation rejects it before the explicit ownership check.
- **Implications:** Security outcome is correct (the write is denied and no request id is returned), but the status code may be misleading to clients and tests. Changing to `403` could confirm that the target identifier exists, so the message must remain generic.
- **Recommended resolution:** Approve either `400` as an intentionally opaque validation rejection or `403` with a generic permission message and no identifier echo. If `403` is chosen, adjust authorization ordering or the visible queryset carefully without weakening RLS or revealing hospital existence.
- **Implementation status:** Not implemented.

### 4.5 Request PATCH permissions

- **Observed (B-06B D16):** An admin PATCH can change `hospital_id`. There is no field-level restriction limiting PATCH to status/units/notes.
- **Implications:** Reassigning a request’s hospital can affect isolation, reporting, and audit attribution. Hospital users are still blocked from cross-hospital changes.
- **Recommended resolution:** Approve whether `hospital_id` is immutable after creation. If immutable, restrict it to create-only; if reassignment is required, make it an explicit admin-only operation with an audit trail.
- **Implementation status:** Not implemented.

### 4.6 Frontend route protection

- **Observed:** Static review shows `frontend/components/ProtectedRoute.tsx` correctly redirects unauthenticated and recovery sessions and enforces `allowedRoles`. Dashboard, donors/new, requests list, analytics, hospitals, and profile pages use it. `frontend/app/requests/new/page.tsx` does **not** import or wrap its form in `ProtectedRoute`.
- **Verified limitation:** F1–F4 were not executed because no approved browser/E2E driver or browser executable was available. The missing guard on `requests/new` is therefore a **static observation only**, not a runtime-verified defect. API-side authorization still applies to the create request.
- **Implications:** An unauthenticated or wrong-role user may see a form or loading/error state that should be guarded, even though the API rejects the write. This is a UX/defense-in-depth gap, not an API security bypass.
- **Recommended resolution:** After browser capability is approved, verify route behavior. If confirmed, wrap the route with the appropriate guard and add a UI regression test. Keep server-side enforcement as the primary control.
- **Implementation status:** Not implemented.

## 5. Prioritized findings

| ID | Finding | Classification | Priority | Rationale |
|---|---|---|---|---|
| DR-01 | Oversized request notes produce 500 | Medium / confirmed defect | P1 | User-visible invalid-input handling defect; no leakage or persistence failure. |
| DR-02 | Cross-hospital create/PATCH returns 400 instead of 403 | Product decision | P2 | Denial works; status semantics need approval. |
| DR-03 | Status transitions unrestricted | Product decision | P2 | Workflow/auditability rule missing. |
| DR-04 | Blood-type compatibility unrestricted | Product decision | P2 | Clinical/data-quality rule missing. |
| DR-05 | Admin PATCH can change hospital | Product decision | P2 | Isolation/audit semantics need approval. |
| DR-06 | Frontend route guard on `requests/new` absent statically | Testing limitation | P2 | Static observation only; API controls passed. |
| DR-07 | `IsHospitalUser` defined but unused | Low / hardening observation | P3 | No current exposure; dead or future control needs a decision. |
| DR-08 | Ineligible-donor error echoes a donor identifier | Low / hardening observation | P3 | Not sensitive credentials; unnecessary client detail. |
| DR-09 | A10 not executable as defined | Testing limitation | P2 | No endpoint or expected behavior exists for an `IsHospitalUser` check. |
| DR-10 | F1–F4 frontend workflows not executed | Testing limitation | P2 | Driver unavailable; API-side workflow coverage exists. |

No findings were classified Critical or High.

## 6. Prioritized remediation plan

### 6.1 Confirmed defect

| Field | DR-01 plan |
|---|---|
| Finding ID | DR-01 / BUG-1 |
| Affected files and functions | `backend/requests_app/serializers.py::BloodRequestSerializer` (`notes` field and `Meta.extra_kwargs`, plus create/update validation path); `backend/requests_app/models.py::BloodRequest.notes`; `backend/requests_app/tests/test_api.py` (missing boundary coverage); schema reference `supabase/migrations/0002_tables.sql::requests_notes_length`. |
| Root cause | The API does not enforce the database’s 1000-character notes limit before write, so a validator-level invalid request reaches the database CHECK and surfaces as an unhandled 500. |
| Recommended correction | Add a serializer-level maximum length of 1000 for `notes` on both create and update, returning `400/validation_error` with a `notes` field error. Keep the database CHECK constraint unchanged. Consider a shared constant so API and schema expectations remain visible together. Do not change the generic 500 envelope. |
| Required regression tests | 1) POST with exactly 1000 characters succeeds. 2) POST with 1001 characters returns `400/validation_error` with `details.notes`. 3) PATCH at 1000 succeeds. 4) PATCH at 1001 returns the same 400. 5) Null/blank notes remain accepted. 6) Admin and hospital roles produce the same validation result. 7) Direct SQL beyond the limit is still rejected by the database constraint. 8) Generic 500 responses still contain no SQL, stack trace, secret, or identifier leakage. |
| Potential risks | Client-visible validation behavior changes from 500 to 400; a future schema limit change could drift from the serializer constant; existing rows longer than the limit could complicate broader validation if a model-level validator is added. |
| Dependencies | Approval of product decision #2 (notes/name lengths); isolated local database for verification; no hosted Supabase or production access. |
| Implementation status | Not implemented in B-07A. |

### 6.2 Conditional follow-ups — require approval, not authorized here

| Related ID | Conditional action | Dependencies |
|---|---|---|
| DR-02 | If `403` is approved, adjust validation/authorization ordering or the visible hospital queryset while preserving RLS and generic messaging. | Product decision #4; explicit tests for both status and non-disclosure. |
| DR-06 | If browser verification confirms the static observation, wrap `requests/new` with `ProtectedRoute` and add a UI regression test. | Approved browser driver; product decision #6. |
| DR-07 / DR-09 | Decide whether `IsHospitalUser` should be applied to a defined hospital-only endpoint, retained for future use, or removed as dead code. | Product/API design decision; A10 scenario definition. |
| DR-08 | If approved, omit the donor identifier from the `ineligible_donor` error body while retaining days-until-eligible and badge. | Product approval; frontend error-handling check. |

## 7. Regression testing matrix

Priorities: P0 = security/isolation gate, P1 = core workflow gate, P2 = UX/product-decision gate.

| Priority | Area | Scenario | Expected result | Evidence/source to reuse |
|---|---|---|---|---|
| P0 | Authentication | Missing, malformed, expired, wrong-audience, wrong-issuer, unsupported-algorithm, and invalid-subject bearer tokens | `401/authentication_failed`; no token or claim echoed | A1, A2; `authentication/tests/test_auth.py` |
| P0 | Authentication | Valid token with misleading JWT `role` claim or body `role` field | Role resolved from profile table; no privilege change | A3–A6; BREAK-IT attempt 3; `test_auth.py` |
| P0 | Admin/hospital authorization | Hospital accesses donor/hospital admin endpoints and admin-only mutations | `403/permission_denied` | A7–A9; donor/hospital API tests |
| P0 | Hospital isolation | Hospital lists requests and reads another hospital’s detail URL | Only own rows; cross-hospital detail `404/not_found` | E1, E3; `requests_app/tests/test_api.py` |
| P0 | Hospital isolation | Hospital PATCHes or creates for another hospital | Denied; no created or modified request id returned; status per approved decision #4 | D4, D15; `test_hospital_cannot_create_for_another_hospital` |
| P0 | Hospital isolation | Direct SQL attempt to cross hospital request policy | Database rejects or filters; no committed change | E7; RLS verification SQL; `test_rls.py` |
| P0 | Validation/errors | Oversized request notes at 1000/1001 on POST and PATCH | 400 with `notes` field for 1001; no SQL/stack/secret in any envelope | DR-01 regression plan; E10, E11 |
| P1 | Donor management | Admin create/read/update/delete donor; hospital denied mutation | Admin 201/200/204; hospital 403; server-generated eligibility fields unchanged | B1, B2, B8, B9; donor API tests |
| P1 | Donor management | Invalid phone, name, blood type, future date, duplicate normalized phone | `400/validation_error` with correct field | B3–B7; donor API tests |
| P1 | 90-day eligibility | Boundary donors at no history, 0, 89, 90, and 120 days | Correct eligible flag, badge, and days fields | C1–C6 |
| P1 | 90-day eligibility | Attach ineligible donor to a request directly via API | `400/ineligible_donor`; days-until eligible and badge; no request created | D10; `test_ineligible_donor_is_rejected_with_400` |
| P1 | Donor privacy | Hospital reads ineligible donor; admin reads same donor; hospital reads eligible donor | Hospital gets null phone only for ineligible donor; admin sees phone | C8; `test_phone_redaction_for_hospital` |
| P1 | Blood requests | Create with server-set hospital/requester; admin create with explicit hospital | 201; hospital and requester match policy | D1, D2; request API tests |
| P1 | Blood requests | Invalid units, blood type, status; invalid hospital id | `400/validation_error` with field | D3, D5–D8 |
| P1 | Blood requests | Request-to-donor deletion behavior and hospital deletion restriction | Donor delete sets request donor null; hospital delete restricted | E5, E6, E7 |
| P1 | Analytics/isolation | Hospital and admin summary totals over seeded disposable records | Hospital excludes other-hospital data; admin includes all visible rows | E4 |
| P2 | Product decisions | Status transitions per approved state machine | Only approved transitions accepted | D12–D14; decision #1 |
| P2 | Product decisions | Blood-type compatibility per approved rule | Mismatch allowed with warning or rejected as specified | D11; decision #3 |
| P2 | Product decisions | Admin PATCH scope per approved field policy | `hospital_id` immutable or explicitly admin-governed | D16; decision #5 |
| P2 | Frontend workflows | F1 donor registration/detail, F2 eligibility badges, F3 request creation, F4 route guards | Each workflow PASS in browser after driver approval | F1–F4; decision #6 |
| P2 | Frontend route guard | Unauthenticated/wrong-role access to `requests/new` | Redirect or access-denied state consistent with other guarded routes | Static DR-06 observation; F4 |

## 8. Remaining blockers

1. **Browser automation unavailable.** F1–F4 remain BLOCKED. The repository has `vitest`, `jsdom`, and Testing Library dependencies and some component/unit tests, but no approved browser/E2E driver or browser executable was available for the B-06B run. No UI workflow is treated as verified here.
2. **Six product decisions unapproved.** Observed behaviors in D4, D11, D13, D14, D16, and frontend routing cannot become requirement-based PASS/FAIL assertions until product intent is approved.
3. **A10 has no executable definition.** No endpoint uses `IsHospitalUser`, and B-06B recorded expected result as `N/A`. A10 cannot be executed as an authorization scenario without a defined endpoint and expected behavior.
4. **Hosted/production behavior out of scope.** Real Supabase Auth flows, live JWKS verification, deployed configuration, and hosted RLS enforcement were not assessed. No hosted database was accessed.
5. **Fixes not implemented or retested.** DR-01 and all conditional follow-ups are plans only. No code, test, configuration, environment, migration, or RLS changes were made.
6. **Pre-existing untracked file.** `backend/b05b7_r.py` remains pre-existing and untracked; it was not opened for execution or modified.

## 9. Recommended next step

Approve the six product decisions first, especially decision #2 (notes/name lengths). Then implement DR-01 in a separate authorized change: add serializer-level notes-length validation, add the boundary regression tests listed above, and rerun P0/P1 regression cases on the isolated local stack. After an approved browser driver is available, execute F1–F4 and verify the static `requests/new` route-guard observation. Keep all hosted Supabase and production systems out of scope unless explicitly authorized.

## 10. B-07A verification

- This report was prepared using read-only inspection only.
- No application code, tests, configuration, environment files, migrations, database rows, or RLS policies were changed.
- No commit, push, deployment, or hosted/production access was performed.
- No credentials, tokens, UUIDs, phone numbers, email addresses, database URLs, or secret values are reproduced in this report.
- Repository state was checked after preparation; no implementation changes were introduced by B-07A.
