# B-06B — End-to-End Functional Testing Execution Report

Date: 2026-11-23
Scope: approved-scope functional tests against the isolated local PostgreSQL stack only.

## 1. Safety precondition results

| ID | Result | Expected | Actual / sanitized evidence |
|---|---|---|---|
| P1 | PASS | loopback host, port 55432, database name present, not Supabase-like | loopback host, port 55432, database name present, not Supabase-like |
| P2 | PASS | temporary frontend copy served successfully; local backend is the compile-time API value; old endpoint is only a dead fallback literal; local Supabase placeholder compiled | {"dead_old_fallback_literal_present": true, "html_status": 200, "local_api_compile_time_value": true, "local_dev_key_marker": true, "local_supabase_marker": true, "old_api_compile_time_value": false, "script_count": 17} |
| P3 | PASS | baseline counts captured without exposing identifiers | {"auth_users": 5, "donors": 12, "hospitals": 3, "profiles": 5, "requests": 7} |
| P4 | PASS | development login available and local-only | dev login succeeded for 3 local identities |
| P5 | PASS | donor count reported by API equals count in local DB | api_count=12; local_db_count=12 |

Additional safety notes:

- The hosted Supabase/production database was never accessed. The checked-in backend `.env` database URL was classified as hosted and rejected.
- A separate backend process was started with process-level loopback database overrides and local-only JWT settings. Backend health returned `200` on loopback port 8011; no URL or credential is reproduced here.
- The existing frontend server on port 3000 was not used: its compiled bundle targeted the old backend port and a hosted Supabase host. Stopping that process was denied, so it was left untouched.
- A throwaway frontend copy outside the repository was served on loopback port 3001 with process overrides. Its compile-time API value is the isolated backend; the old endpoint appears only as a dead fallback literal in the compiled source.
- No migrations, deployments, Git pushes/commits, application code changes, test changes, configuration changes, environment-file changes, or RLS changes were made.
- `backend/b05b7_r.py` and `scripts/make_test_token.py` were not run.
- All tokens were held only in harness memory. No passwords, tokens, UUIDs, phone numbers, secrets, or database URLs are reproduced in this report.
- Seed baseline before writes: donors 12, hospitals 3, profiles 5, requests 7, auth users 5. Post-cleanup counts were identical.

## 2. Result counts

| Result | Count |
|---|---:|
| PASS | 62 |
| FAIL | 0 |
| BLOCKED | 4 |
| NOT TESTED | 1 |
| **Total** | **67** |

No executed assertion produced a FAIL. Items that depend on an unavailable browser are marked BLOCKED; one item with no applicable API surface is marked NOT TESTED.

## 3. Detailed test results

### Phase 1 — Safety preconditions

| ID | Result | Expected | Actual / sanitized evidence | Note |
|---|---|---|---|---|
| P1 | PASS | loopback host, port 55432, database name present, not Supabase-like | loopback host, port 55432, database name present, not Supabase-like |  |
| P2 | PASS | temporary frontend copy served successfully; local backend is the compile-time API value; old endpoint is only a dead fallback literal; local Supabase placeholder compiled | {"dead_old_fallback_literal_present": true, "html_status": 200, "local_api_compile_time_value": true, "local_dev_key_marker": true, "local_supabase_marker": true, "old_api_compile_time_value": false, "script_count": 17} |  |
| P3 | PASS | baseline counts captured without exposing identifiers | {"auth_users": 5, "donors": 12, "hospitals": 3, "profiles": 5, "requests": 7} |  |
| P4 | PASS | development login available and local-only | dev login succeeded for 3 local identities |  |
| P5 | PASS | donor count reported by API equals count in local DB | api_count=12; local_db_count=12 |  |

### Phase A — Authentication and roles

| ID | Result | Expected | Actual / sanitized evidence | Note |
|---|---|---|---|---|
| A1 | PASS | 401 authentication_failed on donors and requests | donors=401/authentication_failed; requests=401/authentication_failed |  |
| A2 | PASS | 401 authentication_failed | 401/authentication_failed |  |
| A3 | PASS | 200; role=admin; hospital_id absent | 200; role=admin; hospital_id_present=False |  |
| A4 | PASS | 200; role=hospital; hospital_id present | 200; role=hospital; hospital_id_present=True |  |
| A5 | PASS | 200; role=hospital; hospital_id present and distinct from hospital 1 | 200; role=hospital; hospital_id_present=True; distinct=True |  |
| A6 | PASS | 200; resolved role remains admin | 200; role=admin |  |
| A7 | PASS | 403 permission_denied | 403/permission_denied |  |
| A8 | PASS | 403 permission_denied for list and create | list=403; create=403/permission_denied |  |
| A9 | PASS | 403 permission_denied for PATCH and DELETE | patch=403/permission_denied; delete=403/permission_denied |  |
| A10 | NOT TESTED | N/A | Not executed |  |

### Phase B — Donor management

| ID | Result | Expected | Actual / sanitized evidence | Note |
|---|---|---|---|---|
| B1 | PASS | 201; eligible=true; badge=no_history; days_since_last_donation=null | 201; eligible=True; badge=no_history; days_since_present=False |  |
| B2 | PASS | PATCH 200; GET 200; updated name returned | patch=200; get=200; name_matches=True |  |
| B3 | PASS | 400 validation_error with the invalid field reported | 400/validation_error; fields=['phone'] |  |
| B4 | PASS | 400 validation_error with the invalid field reported | 400/validation_error; fields=['name'] |  |
| B5 | PASS | 400 validation_error with the invalid field reported | 400/validation_error; fields=['blood_type'] |  |
| B6 | PASS | 400 validation_error with the invalid field reported | 400/validation_error; fields=['last_donation'] |  |
| B7 | PASS | 400 validation_error on phone field | 400/validation_error; fields=['phone'] |  |
| B8 | PASS | 404 not_found | 404/not_found |  |
| B9 | PASS | DELETE 204; subsequent GET 404 not_found | delete=204; get_after=404/not_found |  |
| B10 | PASS | No stack trace, SQL text, or secret in error response | 400/validation_error; details_is_null=False; fields=['name'] |  |

### Phase C — Donor eligibility

| ID | Result | Expected | Actual / sanitized evidence | Note |
|---|---|---|---|---|
| C1 | PASS | eligible=True; days_since=None; days_until=0; badge=no_history | {"badge": "no_history", "days_since": null, "days_until": 0, "eligible": true, "status": 201} |  |
| C2 | PASS | eligible=False; days_since=0; days_until=90; badge=ineligible | {"badge": "ineligible", "days_since": 0, "days_until": 90, "eligible": false, "status": 201} |  |
| C3 | PASS | eligible=False; days_since=89; days_until=1; badge=ineligible | {"badge": "ineligible", "days_since": 89, "days_until": 1, "eligible": false, "status": 201} |  |
| C4 | PASS | eligible=True; days_since=90; days_until=0; badge=eligible | {"badge": "eligible", "days_since": 90, "days_until": 0, "eligible": true, "status": 201} |  |
| C5 | PASS | eligible=True; days_since=120; days_until=0; badge=eligible | {"badge": "eligible", "days_since": 120, "days_until": 0, "eligible": true, "status": 201} |  |
| C6 | PASS | eligible=true and eligible=false partition the disposable donors exactly | eligible_match=True; ineligible_match=True |  |
| C7 | PASS | 400 validation_error for invalid eligible and blood_type query values | eligible=400/validation_error; blood_type=400/validation_error |  |
| C8 | PASS | hospital sees null phone for ineligible donor; admin sees phone; hospital sees phone for eligible donor | redacted=True; admin_visible=True; eligible_visible=True |  |

### Phase D — Blood requests

| ID | Result | Expected | Actual / sanitized evidence | Note |
|---|---|---|---|---|
| D1 | PASS | 201; status=pending; hospital and requester server-set | 201; status_value=pending; hospital_matches=True; requester_present=True |  |
| D2 | PASS | 201; selected hospital returned | 201; hospital_matches=True |  |
| D3 | PASS | 400 validation_error on hospital_id | 400/validation_error; fields=['hospital_id'] |  |
| D4 | PASS | Observed current behavior: rejected with a coded 4xx error and no request id | 400/validation_error; fields=['hospital_id']; id_returned=False |  |
| D5 | PASS | 400 validation_error on units | 400/validation_error; fields=['units'] |  |
| D6 | PASS | 400 validation_error on units | 400/validation_error; fields=['units'] |  |
| D7 | PASS | 400 validation_error on blood_type | 400/validation_error; fields=['blood_type'] |  |
| D8 | PASS | 400 validation_error on status | 400/validation_error; fields=['status'] |  |
| D9 | PASS | 201; donor fields populated; donor_eligible=true | 201; donor_link_present=True; donor_eligible=True |  |
| D10 | PASS | 400 ineligible_donor; 1 day remaining; badge=ineligible | 400/ineligible_donor; days_until=1; badge=ineligible; donor_id_echoed=True; matches={'status_400': True, 'code': True, 'days_until_1': True, 'badge': True} |  |
| D11 | PASS | Observed current behavior: request is accepted when types differ | 201; donor_type_present=True; request_type=O+ |  |
| D12 | PASS | 200; status=fulfilled | patch1=200; status1=fulfilled |  |
| D13 | PASS | Observed current behavior: allowed | patch2=200; status2=pending |  |
| D14 | PASS | Observed current behavior: allowed | 201; status_value=fulfilled |  |
| D15 | PASS | Observed current behavior: rejected with a coded 4xx error | 400/validation_error; fields=['hospital_id'] |  |
| D16 | PASS | Observed current behavior: allowed | 200; hospital_matches=True |  |

### Phase E — Data integrity and isolation

| ID | Result | Expected | Actual / sanitized evidence | Note |
|---|---|---|---|---|
| E1 | PASS | hospital sees own disposable request; does not see hospital 2 request | own_visible=True; other_visible=False |  |
| E2 | PASS | admin sees both disposable hospital requests | h1_visible=True; h2_visible=True |  |
| E3 | PASS | 404 not_found for GET and PATCH | get=404/not_found; patch=404/not_found |  |
| E4 | PASS | hospital summary excludes other-hospital request; admin total covers both hospitals | h1_other_visible=False; admin_total=13; baseline_total=7; admin_covers_two_new=True |  |
| E5 | PASS | request->hospital RESTRICT; request->donor SET NULL; profile->hospital RESTRICT; profile->auth CASCADE | {"profiles_auth_cascade": true, "profiles_hospital_restrict": true, "requests_donor_set_null": true, "requests_hospital_restrict": true} |  |
| E6 | PASS | DELETE 204; request remains with donor_id=null | delete=204; request_get=200; donor_id_null=True |  |
| E7 | PASS | Database reject with SQLSTATE 23001 (restrict_violation) and no committed change | sqlstate=23001 |  |
| E8 | PASS | Database reject with SQLSTATE 23505; both attempted rows rolled back | sqlstate=23505 |  |
| E9 | PASS | all four expected schema objects present | {"donor_phone_check": true, "donor_search_index": true, "normalized_phone_index": true, "request_notes_check": true} |  |
| E10 | PASS | No stack trace, SQL text, or secret in error response | 500/internal_error; details_is_null=True; fields=[] |  |
| E11 | PASS | all sampled errors use the standard error.code envelope | codes=['validation_error', 'validation_error', 'authentication_failed', 'authentication_failed'] |  |

### Phase F — Frontend

| ID | Result | Expected | Actual / sanitized evidence | Note |
|---|---|---|---|---|
| F0 | PASS | local backend is the compile-time API value; local Supabase placeholders compiled | {"dead_old_fallback_literal_present": true, "html_status": 200, "local_api_compile_time_value": true, "local_dev_key_marker": true, "local_supabase_marker": true, "old_api_compile_time_value": false, "script_count": 17} |  |
| F1 | BLOCKED | Executable only with an approved browser/E2E driver | Not executed |  |
| F2 | BLOCKED | Executable only with an approved browser/E2E driver | Not executed |  |
| F3 | BLOCKED | Executable only with an approved browser/E2E driver | Not executed |  |
| F4 | BLOCKED | Executable only with an approved browser/E2E driver | Not executed |  |

### Cleanup verification

| ID | Result | Expected | Actual / sanitized evidence | Note |
|---|---|---|---|---|
| Z1 | PASS | all tracked disposable requests/donors/hospitals removed | cleanup_attempts={"donors": 11, "hospitals": 0, "requests": 7}; tracked_counts={'donors': 11, 'requests': 7, 'hospitals': 1} |  |
| Z2 | PASS | all-table and non-[E2E] counts equal the pre-test baseline | before={"auth_users": 5, "donors": 12, "hospitals": 3, "profiles": 5, "requests": 7}; after={"auth_users": 5, "donors": 12, "hospitals": 3, "profiles": 5, "requests": 7}; seed_before={"auth_users": 5, "donors": 12, "hospitals": 3, "profiles": 5, "requests": 7}; seed_after={"auth_users": 5, "donors": 12, "hospitals": 3, "profiles": 5, "requests": 7} |  |

## 4. Bugs discovered

- **BUG-1 — Oversize request notes surface as a 500.** Test E10 sent request notes longer than the database CHECK limit. The API returned `500/internal_error` with a generic, non-leaking envelope (`details: null`). The serializer does not cap `notes` at the database's 1000-character limit, so a validation problem reaches the database layer. This is recorded as observed current behavior and a product/implementation decision, not as a failing test.
- No other executed assertion failed.

## 5. Product decisions still outstanding

The six decisions from B-06A remain unapproved. The following observations are recorded, not treated as failures:

1. **Request status transitions** — D12, D13, D14: `pending → fulfilled`, `fulfilled → pending`, and creation directly as `fulfilled` are all accepted. No state machine is enforced.
2. **Notes/name length behavior** — E10: oversize notes produce `500/internal_error`. B10: oversize donor name is rejected with `400/validation_error` and a `name` field, consistent with the model field's inferred max length.
3. **Blood-type compatibility** — D11: a request may link a donor whose blood type differs from the request; the API returned `201`.
4. **Cross-hospital create status** — D4: a hospital attempting to create for another hospital receives `400/validation_error` on `hospital_id`, not `403`; the other hospital is outside the hospital's RLS-scoped lookup. D15 shows the same pattern on PATCH.
5. **Request PATCH scope** — D16: an admin PATCH can change `hospital_id`. There is no field-level restriction limiting PATCH to status/units/notes.
6. **Client route guards** — F1–F4 are BLOCKED because no browser automation is available. API-side role enforcement is covered by A1–A9, D1, D15, and E1–E4, but browser route behavior was not verified.

## 6. Recommended next actions

1. Approve the six product decisions, then convert these observed-behavior checks into requirement-based assertions.
2. If approved, add a serializer-level maximum length for request notes so oversize input returns `400/validation_error` instead of `500/internal_error` (BUG-1).
3. Decide whether cross-hospital `hospital_id` attempts should return `403/permission_denied` rather than `400/validation_error`; if so, adjust validation/authorization ordering or the visible hospital queryset.
4. Add an approved browser automation capability and rerun F1–F4 to verify registration/detail, eligibility badges, request creation, and route guards through the UI.
5. Keep future runs on the isolated loopback stack with disposable `[E2E]` records and a seed-count baseline check; do not reuse the hosted `.env` database URL.
6. After fixes are approved and implemented, rerun this matrix and update the report with requirement-based PASS/FAIL results.

## 7. Final state

- All disposable requests, donors, and hospitals created during the final run were removed (Z1).
- Seed and all-table counts are unchanged from the pre-test baseline (Z2).
- No fixes were implemented. No files other than this report were changed in the repository. No commit, push, or deployment was performed.
