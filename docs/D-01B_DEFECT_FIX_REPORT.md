# D-01B — Defect Fix Report

Date: 2026-11-23
Task: implement DR-01 validation fix and regression tests
Authorization: serializer change, R1–R9 tests, and isolated-local automated tests only

## 1. Outcome

DR-01 / BUG-1 is **resolved in the working tree** and verified against the isolated local test database.

Oversized request notes now fail serializer validation with `400/validation_error` and a `notes` field detail instead of reaching the database CHECK constraint and returning `500/internal_error`.

No commit, push, staging, reset, stash, discard, deployment, service creation, production database access, environment-file change, migration change, or RLS policy change was performed.

## 2. Root cause

`BloodRequestSerializer` declared `notes` as optional, blankable, and nullable, but did not declare a maximum length. The database migration owns the real limit:

`supabase/migrations/0002_tables.sql` → `requests_notes_length CHECK (notes IS NULL OR length(notes) <= 1000)`

Before the fix:

1. DRF generated an unbounded `CharField`/`TextField` validator for `notes`.
2. `is_valid()` accepted values longer than 1000 characters.
3. `create()` or `update()` attempted the database write.
4. PostgreSQL rejected the write with the CHECK constraint.
5. No application layer converted that error into field validation.
6. `common.errors.api_exception_handler` returned the generic `500/internal_error` envelope observed in B-06B E10.

## 3. Files changed

| File | Change |
|---|---|
| `backend/requests_app/serializers.py` | Added `max_length: 1000` to `BloodRequestSerializer.Meta.extra_kwargs["notes"]`. |
| `backend/requests_app/tests/test_api.py` | Added nine R1–R9 regression tests plus a small shared validation-error assertion helper and two test constants. |
| `docs/D-01B_DEFECT_FIX_REPORT.md` | Created this report. |

No migration, model, view, policy, settings, environment, frontend, or unrelated test file was changed.

## 4. Implementation details

The serializer field options are now:

```python
"notes": {
    "required": False,
    "allow_blank": True,
    "allow_null": True,
    "max_length": 1000,
},
```

Preserved behavior:

- `notes` remains optional.
- `null` and blank strings remain accepted.
- Existing ownership checks and hospital-scoped querysets are unchanged.
- Admin and hospital write paths use the same validation.
- The database CHECK constraint remains the defense-in-depth control.
- Generic 500 handling for genuinely unhandled errors is unchanged.

The change is confined to the serializer field, so it applies to both POST and PATCH without view or model changes.

## 5. R1–R9 regression results

Final result: **9 run, 9 PASS, 0 FAIL**.

| ID | Test | Result | Verified behavior |
|---|---|---|---|
| R1 | `test_r1_post_notes_at_limit_succeeds` | PASS | POST with exactly 1000 characters returns 201; response and stored row preserve the full value. |
| R2 | `test_r2_post_notes_over_limit_returns_validation_error` | PASS | POST with 1001 characters returns 400/`validation_error`, reports `notes`, returns no id, and creates no oversized-note row. |
| R3 | `test_r3_patch_notes_at_limit_succeeds` | PASS | PATCH with exactly 1000 characters returns 200 and stores the full value. |
| R4 | `test_r4_patch_notes_over_limit_preserves_stored_value` | PASS | PATCH with 1001 characters returns 400/`validation_error` and leaves the stored value unchanged. |
| R5 | `test_r5_null_and_blank_notes_remain_valid` | PASS | POST and PATCH accept both `null` and `""` with unchanged storage semantics. |
| R6 | `test_r6_oversize_notes_validation_is_role_independent` | PASS | Hospital and admin roles both receive 400/`validation_error` on oversized POST and PATCH. |
| R7 | `test_r7_database_still_rejects_oversize_notes` | PASS | Direct model write with 1001 characters is rejected by the database constraint; no row exceeding 1000 characters remains. |
| R8 | `test_r8_unicode_notes_use_character_count` | PASS | 1000 Unicode characters are accepted; 1001 Unicode characters are rejected with 400/`validation_error`. |
| R9 | `test_r9_oversize_notes_error_envelope_does_not_leak_details` | PASS | Error code/message are correct and the payload contains no SQL, stack-trace, constraint-name, credential, or secret fragments. |

Test-authoring notes:

- An initial R2 assertion compared global request counts before and after an authenticated POST. That was invalid because the auth middleware changes the RLS claim context mid-test, which changes the visible count. The assertion was replaced with a direct check that no oversized-note row was created.
- A full-suite run initially used a wrapper that cleared Supabase issuer settings, causing an unrelated wrong-issuer auth test to pass a bad token. The wrapper was corrected to leave authentication settings as the project expects; the final full-suite result below is from that corrected run.

## 6. Existing regression results

All commands ran with `DJANGO_DEBUG=true`, the test-only database URL loaded from the local environment, and `DATABASE_URL` overridden to that same local target so no hosted database could be reached.

| Check | Result |
|---|---|
| New R1–R9 tests only | `Ran 9 tests` — `OK` |
| `requests_app.tests.test_api` | `Ran 22 tests` — `OK` (13 existing + 9 new) |
| Full backend suite | `Ran 107 tests` — `OK` |
| Django system checks | `System check identified no issues (0 silenced).` |
| `git diff --check` | No whitespace errors; two LF-to-CRLF informational warnings for the modified files |

No executed final assertion failed.

## 7. Database safety verification

The isolated database was verified before any test command:

| Control | Result |
|---|---|
| `TEST_DATABASE_URL` present | PASS |
| `DJANGO_DEBUG=true` | PASS |
| Configured host is loopback | PASS |
| Configured port is the local isolated port | PASS |
| Configured database name present | PASS |
| Hosted-marker strings absent from the local test URL | PASS |
| Server reports loopback address | PASS |
| Server reports the isolated local port | PASS |
| Server database name matches the configured local name | PASS |
| Local PostgreSQL answers a direct connectivity probe | PASS |

Output was limited to sanitized PASS-style evidence; no connection string, credential, token, or identifier was printed.

Additional safety controls:

- No standalone `manage.py migrate` or `apply-local-migrations.ps1` command was run.
- The project's required `DomainSchemaTestRunner` created a disposable local test database and tore it down after each run. Its standard setup applied built-in Django app migrations and the checked-in Supabase SQL schema files to that disposable database only.
- No migration was applied to the seeded local database or to any hosted/production database.
- No hosted Supabase credential, production user record, or production PostgreSQL connection was used.
- All test records were created inside `APITestCase` transactions and rolled back; the disposable test database was destroyed after each run.
- Generated tokens came from existing local test helpers using the clearly-marked development secret.

## 8. Git status

At completion:

| Item | State |
|---|---|
| Branch | `main` |
| HEAD | `351c66be5ab821285e23d1fe2aab6f3ebbd72f1b` |
| Upstream | `origin/main`, aligned with HEAD |
| Tracked modifications | `backend/requests_app/serializers.py`, `backend/requests_app/tests/test_api.py` |
| Staged changes | None |
| Commit/push/reset/stash/discard | None performed |
| Preserved untracked files | `backend/b05b7_r.py`, `docs/B-06B_E2E_TEST_REPORT.md`, `docs/B-07A_DEFECT_REVIEW_REPORT.md`, `docs/D-01_DEPLOYMENT_READINESS_REPORT.md`, `docs/D-01A_RELEASE_GATE_REPORT.md`, and this report |

`git diff --stat` for tracked changes: 2 files changed, 184 insertions, 1 deletion.

## 9. Remaining blockers

DR-01 is no longer a code blocker in the working tree, but the release gate remains open until:

1. An authorized owner reviews and commits the two approved code/test changes and decides which audit reports belong in the release commit.
2. The release SHA is recorded and the R1–R9 plus P0/P1 regression checks are rerun against that exact commit if required by the release process.
3. Render and Vercel environment variables, runtime pins, origins, and custom domains are configured.
4. Hosted Supabase JWT/JWKS, redirect, migration state, and RLS enforcement are verified in an approved environment.
5. Linux Gunicorn startup on Render is verified during a controlled build/deployment window.
6. Frontend workflow tests F1–F4 are executed once an approved browser/E2E driver is available.
7. Optional frontend UX: add a visible 1000-character hint or `maxLength` to the request notes field so users receive early feedback; server-side validation remains authoritative.

## 10. Verification statement

- Only the approved serializer and request test files were modified.
- No secrets, tokens, database URLs, UUIDs, email addresses, phone numbers, or production host identifiers are reproduced in this report.
- No deployment, service creation, production access, commit, push, staging, reset, stash, or discard was performed.
