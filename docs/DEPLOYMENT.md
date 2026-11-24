# Production deployment runbook

This repository deploys as three separate services:

```text
Browser ──> Vercel (Next.js) ──> Render (Django REST API) ──> Supabase PostgreSQL
                  └────────────> Supabase Auth
```

This guide describes the repository configuration. A successful local build does not
confirm that production credentials, hosted database policies, or live services work.
Do not deploy a branch until its commit has been reviewed and selected for production.

## Render: Django API

Create a Render **Web Service** from the approved GitHub repository and branch:

| Setting | Value |
|---|---|
| Root Directory | `backend` |
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT` |
| Health Check Path | `/health` |
| Python version | `3.14.10` (`PYTHON_VERSION`) |

Set these variables in the Render service environment. Enter secret values in Render's
secret store; do not put them in Git or Vercel.

| Variable | Requirement |
|---|---|
| `DJANGO_DEBUG` | `false` |
| `DJANGO_SECRET_KEY` | Required; generate a unique, strong value |
| `DJANGO_ALLOWED_HOSTS` | Exact Render hostname, without `https://` |
| `DATABASE_URL` | Supabase PostgreSQL connection string for a least-privilege app role; include `sslmode=require` |
| `CORS_ALLOWED_ORIGINS` | Exact Vercel production origin, including `https://`, no trailing slash |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_JWKS_URL` | Optional; derived from `SUPABASE_URL` when unset |
| `SUPABASE_JWT_ISSUER` | Optional; derived from `SUPABASE_URL` when unset |
| `SUPABASE_JWT_AUDIENCE` | Optional; defaults to `authenticated` |
| `SUPABASE_JWT_SECRET` | Only if the project still uses HS256; otherwise leave unset |
| `CSRF_TRUSTED_ORIGINS` | Leave unset for the current bearer-token API unless a cookie/CSRF flow is added |

Do not set `TEST_DATABASE_URL` on Render. The application requires `DATABASE_URL` and
`DJANGO_SECRET_KEY` when `DJANGO_DEBUG=false`. The database role must be non-superuser,
must not bypass RLS, and must support the app's `SET ROLE authenticated` request flow.
Confirm the Supabase migration state, grants, RLS policies, and pooler mode before using
real data. Do not apply migrations to an existing production database without reviewing
their effects and taking an approved backup.

The domain schema is owned by `supabase/migrations/`, not Django migrations. Consequently,
`python manage.py showmigrations` only reports Django's built-in apps and does not verify
that Supabase SQL migrations `0001`–`0010` are applied. Check the Supabase migration ledger
and schema/RLS state using an authorized dashboard or read-only operator query.

This app parses `DATABASE_URL` with `dj-database-url`, including PostgreSQL URL options.
Use `sslmode=require` so the client refuses an unencrypted connection. This encrypts the
connection but does not verify the server certificate; `verify-full` with the Supabase CA
certificate provides server identity verification. Configure the CA as a protected Render
file if using that stronger mode. The current local connection negotiated TLS with
`sslmode=require`.

The inspected local connection uses Supabase's shared **session** pooler on port `5432`.
That is compatible with Django's request transactions. Prefer direct or session mode for
this persistent Render service. Do not switch this configuration to shared transaction
pooling on port `6543` without further work: Psycopg defaults to preparing statements
after repeated executions, while Supabase's shared transaction pooler does not support
prepared statements. The application has no `prepare_threshold=None` override. If
transaction pooling is selected, add and validate that setting before deployment.
See [Supabase connection modes and SSL](https://supabase.com/docs/guides/database/connecting-to-postgres).

The `/health` endpoint returns application liveness only. It does not check PostgreSQL.

The production-mode Django deployment check currently warns that
`XFrameOptionsMiddleware` and `CsrfViewMiddleware` are absent, HSTS is unset, and
`SECURE_SSL_REDIRECT` is disabled. This is a JSON API using bearer tokens, and the settings
defer HTTPS proxy assumptions to Render. Before go-live, confirm the API is not serving
HTML that needs frame protection, browser auth remains bearer-token based, and Render
enforces HTTPS. Reassess HSTS and proxy-aware redirect settings after confirming Render's
forwarded-protocol behavior; do not enable them blindly.

## Vercel: Next.js frontend

Import the approved repository and branch into Vercel:

| Setting | Value |
|---|---|
| Root Directory | `frontend` |
| Framework Preset | Next.js |
| Install Command | `npm install` |
| Build Command | `npm run build` |
| Output Directory | Next.js default |
| Node.js Version | `22.x` (supported by Vercel; Next.js package requires Node.js `>=20.9.0`) |

Set these variables in the Vercel **Production** environment:

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | `https://blood-donor-registry-pkel.onrender.com` |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` or `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Public publishable/anon key only |
| `NEXT_PUBLIC_ALLOW_DEV_LOGIN` | `false` (or unset) |

Never add `DJANGO_SECRET_KEY`, `DATABASE_URL`, `SUPABASE_JWT_SECRET`, or a Supabase
service-role/secret key to Vercel or any `NEXT_PUBLIC_*` variable.

## Connect the deployed origins

After Vercel has a production URL:

1. Set Render `CORS_ALLOWED_ORIGINS` to that exact origin and ensure
   `DJANGO_ALLOWED_HOSTS` contains the Render hostname.
2. In Supabase Auth, set the Site URL and add the exact Vercel callback URL:
   `https://<actual-vercel-domain>/auth/callback`.
3. Confirm `NEXT_PUBLIC_API_BASE_URL` points to the Render API URL above.
4. Redeploy services after environment changes.

Do not use guessed domains or wildcard CORS/redirects.

## Deploy and verify

1. Review the selected GitHub commit and confirm it contains the intended backend and
   frontend. The local branch/commit may differ from the production branch.
2. Configure and deploy the Render service. Confirm the service is live, then request
   `https://blood-donor-registry-pkel.onrender.com/health`; expect HTTP 200 and
   `{"status":"ok"}`. This verifies liveness only.
3. Configure and deploy the Vercel project. Confirm its deployment status is Ready and
   record its actual production domain.
4. Apply exact origins and Supabase redirect settings as described above.
5. Provision Supabase Auth users and their registry profiles using the approved
   administrator workflow in [`SUPABASE_SETUP.md`](SUPABASE_SETUP.md). The frontend has
   login and password recovery but no self-service account-signup flow. Donor registration
   is a separate authenticated API workflow.
6. With approved test accounts and non-sensitive test records, verify login, donor
   registration, logout, password recovery/callback, role-protected routes, API authorization, CORS,
   donor/hospital/request workflows, database reads/writes, and rejection of unauthorized
   requests. Record outcomes; do not infer database health from `/health`.

## Rollback and troubleshooting

- For an application regression, use the hosting dashboard to restore the previous known
  good Render deployment and Vercel deployment. Confirm that both sides use compatible
  API settings after rollback.
- A code rollback does not reverse database migrations. Handle database rollback only
  through a separately reviewed, backed-up migration plan.
- Render `400` responses can indicate a missing hostname in `DJANGO_ALLOWED_HOSTS`.
  Browser CORS failures require the exact Vercel origin in Render's
  `CORS_ALLOWED_ORIGINS`.
- Login/callback problems require checking the public Supabase URL/key, JWT issuer and
  audience settings, and the exact Auth redirect allowlist.
- A failed build should be diagnosed from the platform build log and reproduced locally
  with `python manage.py check`, `python manage.py check --deploy`, `npm run typecheck`,
  `npm run lint`, and `npm run build`.

## Current verification boundary

Repository checks do not establish the state of Render, Vercel, or hosted Supabase. Before
claiming production readiness, capture the actual production URLs, deployment commit IDs,
health and API results, auth flow results, and database/RLS verification evidence.
