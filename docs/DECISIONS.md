# Engineering Decisions Log

Every non-obvious choice is recorded here so the project can be defended in class.

| # | Decision | Reason | Impact |
|---|---|---|---|
| D1 | Dedicated git repo inside the project folder | The pre-existing git repo root was `C:\Users\user`; committing there would track the whole home directory | `.gitignore` applies only to this project |
| D2 | Isolated temporary Postgres cluster (port 55432, trust auth) instead of the installed cluster | No password for the installed cluster; tests must be reproducible and must not touch user data | Local tests use `postgresql://postgres@127.0.0.1:55432/blood_registry`; production uses `DATABASE_URL` from Supabase |
| D3 | Django 6.1 instead of 5.2 LTS | Python 3.14 is installed; Django 5.2 supports only Python 3.10–3.13 | Documented in README requirements |
| D4 | TypeScript 5.9.3 instead of 7.0.2 | Next 16 toolchain stability | Pinned in package.json |
| D5 | `requests_app` folder name | Avoid shadowing the Python `requests` library on `sys.path` | API URL unchanged: `/api/requests/` |
| D6 | Domain models are `managed = False` | SQL migrations from Supabase are the schema source of truth | `makemigrations` won't generate conflicting table DDL |
| D7 | Role comes from `public.profiles`, not from JWT claims | Supabase's `role` claim means the Postgres role (`authenticated`), not the app role; prevents privilege escalation | Every request does one indexed profile lookup |
| D8 | Support HS256 **and** JWKS-based asymmetric verification | Supabase projects use either legacy HS256 or newer asymmetric signing keys | Config-driven via env vars |
| D9 | Hospital users see phone numbers only for donors that pass the registry screen; admins see all | Minimises sensitive contact data exposure | Implemented in serializers, documented in API docs |
| D10 | Ineligible donor rejection implemented via optional `donor_id` on `POST /api/requests/` | Single server-side choke point; frontend cannot bypass it | Returns 400 with `days_until_eligible` in the error body |
| D11 | `eligibility_badge` string returned by Django and consumed verbatim by the UI | Guarantees the browser never calculates or overrides official status | Values: `eligible`, `ineligible`, `no_history` |
| D12 | Seed data uses relative dates (`CURRENT_DATE - INTERVAL 'n days'`) | The 10-day break-it donor must stay 10 days old forever | Seed is safe to re-run in a fresh DB |
| D13 | 90-day rule is explicitly labelled as a preliminary registry screen | Not a clinical assessment | Stated in API messages, README and UI helper text |
| D14 | Development-only `POST /api/auth/dev-login/` plus `NEXT_PUBLIC_ALLOW_DEV_LOGIN` | No Supabase project was supplied; the full browser → API → DB flow still needed a demonstrable login | Gated by `DJANGO_DEBUG=true`; disabled in production; real deployments use Supabase Auth |
| D15 | Frontend reads the role from `GET /api/auth/me/` after obtaining a token | Keeps the frontend consistent with the server's authoritative role lookup and avoids trusting decoded client claims | Navigation and route guards follow the API profile |
| D16 | `jsdom` pinned to 28.0.0 and `eslint` to 9.39.5 | Node 24.14.1 compatibility and `eslint-config-next@16.4.6` peer range | All frontend checks pass without `--force` |
| D17 | ESLint flat config imports `eslint-config-next` directly | Next 16 ships flat configs; `FlatCompat` produced a circular-config error | `npm run lint` is clean |
| D18 | One `react-hooks/set-state-in-effect` rule exception for data/auth hooks | Initial data loading and Supabase auth bootstrap intentionally synchronise React state with external async systems | Scoped in `frontend/eslint.config.mjs` with an explanatory comment |
| D19 | Do not install `@supabase/server` in this project | The API is Python/Django; `@supabase/server` is a Node/Edge-Function utility. Django verifies Supabase JWTs directly via JWKS | No unnecessary npm dependency in the backend |
| D20 | Support both `NEXT_PUBLIC_SUPABASE_ANON_KEY` and `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | Supabase's newer publishable keys use the `sb_publishable_...` format | Existing env files keep working; publishable keys stay client-safe |
