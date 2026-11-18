# Blood Donor Registry — Development Plan

Status: **Phases 1–7 complete** — local verification passed for database, API and frontend.
This document is the working plan for the whole build. Each phase ends with an executed
verification command; the next phase starts only after that verification passes.

---

## 1. Environment inspection results (executed 2026-11-18)

| Item | Result |
|---|---|
| Project folder | `C:\Users\user\Downloads\Blood Donor Registry` — empty at start |
| OS | Windows 11 (win32), PowerShell |
| Python | 3.14.3 (pip 26.3) |
| Node / npm | v24.14.1 / 11.15.0 |
| Git | 2.51.0.windows.2 — repo root was `C:\Users\user` (home dir) |
| curl | 8.22.0 (`curl.exe`; PowerShell `curl` is an `Invoke-WebRequest` alias) |
| PostgreSQL | 14, 17, 18 installed; `postgresql-x64-18` running, `scram-sha-256` auth, password unknown |
| Network | PyPI + npm registry reachable |
| Supabase credentials | **Not provided** — required only for live deployment, not for local development/tests |

### Consequence for git
A dedicated git repository is initialised **inside the project folder** so `.gitignore`
behaves correctly and the project can be pushed independently. The outer home-directory
repository is left untouched.

### Consequence for testing
An isolated PostgreSQL cluster is created under the approved temp directory
(`C:\Users\user\AppData\Local\Temp\opencode\bdr-pgdata`) on port **55432** with trust
authentication. It is used only to execute the real SQL migrations and the Django test
suite. Nothing is written to the user's existing PostgreSQL 18 cluster.

---

## 2. Pinned, mutually compatible versions

Chosen from live PyPI/npm metadata on 2026-11-18. Python 3.14 requires Django >= 6.0
(Django 5.2 LTS supports only 3.10–3.13), so Django 6.1 is used.

### Backend (`backend/requirements.txt`)
| Package | Pinned version | Reason |
|---|---|---|
| Django | 6.1.3 | Supports Python >= 3.12; current stable line compatible with 3.14 |
| djangorestframework | 3.18.3 | Current DRF, Django 6.x compatible |
| psycopg | 3.3.9 | Modern psycopg 3 driver, explicit transaction control |
| dj-database-url | 3.1.2 | Parse `DATABASE_URL` |
| PyJWT | 2.15.1 | HS256 + JWKS/RS256/ES256 verification |
| cryptography | latest compatible | Required by PyJWT asymmetric algorithms |
| django-cors-headers | 4.9.0 | CORS limited to configured frontend origin |
| python-dotenv | latest | `.env` loading for local development |
| coverage | latest | Test coverage report |

### Frontend (`frontend/package.json`)
| Package | Pinned version |
|---|---|
| next | 16.4.6 |
| react / react-dom | 19.3.1 |
| typescript | 5.9.3 (5.x line — avoids 7.0 toolchain churn) |
| tailwindcss / @tailwindcss/postcss | 4.3.5 |
| @supabase/supabase-js | 2.119.0 |
| recharts | 3.11.0 |
| lucide-react | 1.75.0 |
| vitest / @testing-library/react / jsdom | 5.1.0 / 16.3.3 / 28.0.0 (Node 24 compatible) |
| eslint / eslint-config-next | 9.39.5 / 16.4.6 (peer-compatible) |

---

## 3. Architecture

```
 Next.js 16 (App Router, TS, Tailwind 4)
        │  Supabase JS: email/password login → access_token (JWT)
        │  fetch() with Authorization: Bearer <access_token>
        ▼
 Django 6.1 + DRF 3.18  (REST API + RBAC + eligibility service)
        │  verifies JWT signature/issuer/audience/exp
        │  reads role from public.profiles (never from client claims)
        │  psycopg 3 → DATABASE_URL
        ▼
 Supabase PostgreSQL
   public.hospitals, public.donors, public.profiles, public.requests
   + CHECK / FK / indexes / triggers / RLS policies
   auth.users (Supabase Auth) ← profiles.id references this
```

### Trust boundaries
1. Browser never receives the service-role key or database credentials.
2. Django never trusts a role claim from the JWT or from a request body; the role is
   looked up in `public.profiles` using the verified `sub` claim.
3. `role` and `hospital_id` are excluded from all public profile write serializers.
4. Eligibility is computed only in `backend/donors/services.py`; the browser displays
   the server's `eligible`, `days_until_eligible` and `eligibility_badge` values.
5. RLS policies protect direct Supabase client access; DRF permissions protect the API.

### Database as source of truth
Supabase SQL migrations own the schema of the four domain tables. Django models for those
tables are declared with `managed = False` so `makemigrations` never redefines them.
Django's internal tables (`django_migrations`, `django_session`, …) remain in `public`
with default names — no clash with Supabase's separate `auth` schema.

### Eligibility rule (single implementation)
`last_donation is None` → `eligible = True`, badge `no_history` (preliminary screening only).
Otherwise `eligible = (today - last_donation).days >= 90`.
Boundary cases: 89 → ineligible, 90 → eligible, 120 → eligible.
`days_until_eligible = 90 - days_since` when ineligible, else `0`.

---

## 4. Phase checklist

| Phase | Deliverable | Verification command | Status |
|---|---|---|---|
| 1 | Plan + skeleton + version matrix | folder tree + this doc | ✅ done |
| 2 | SQL migrations, RLS, seed data | isolated Postgres applies migrations; SQL assertions pass | ✅ done |
| 3 | Django API, JWT, RBAC, eligibility, tests | `python manage.py test` — 64 tests pass | ✅ done |
| 4 | Next.js pages/components | `npm run build` + `npm test` — 11 tests pass | ✅ done |
| 5 | Integration: JWT → Django → DB | dev-login + curl assertions in `docs/CURL_TESTS.md` | ✅ done |
| 6 | Sorting, pagination, chart, class activities | Donors page, analytics chart, challenge docs | ✅ done |
| 7 | Full QA, final README/diagrams | README + Mermaid diagrams + all commands green | ✅ done |

---

## 5. Deviations from the requested folder layout (documented decisions)

1. `backend/requests/` → **`backend/requests_app/`**. A folder named `requests` on
   `sys.path` shadows the third-party `requests` package. The API path stays
   `/api/requests/` and the Django app label stays `blood_requests`.
2. `backend/common/` added for shared pagination, error envelopes and DB helpers.
3. `docs/DEVELOPMENT_PLAN.md` and `docs/DECISIONS.md` added for the class workflow.
4. `.env.example` files use placeholder values only — no real keys, no passwords.
