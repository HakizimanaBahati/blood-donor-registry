# D-01 — Deployment Readiness Report

Date: 2026-11-23
Task type: read-only deployment-readiness audit
Target deployment: Next.js frontend on Vercel; Django REST Framework backend on Render

## 1. Executive summary

Deployment readiness is **NEEDS CONFIGURATION**.

The repository contains deployable application structure for both targets: the backend has a Django WSGI entry point, a dependency manifest, a health endpoint, and environment-driven settings; the frontend has a Next.js application, a lockfile, and build scripts. However, neither platform can be considered ready until deployment-specific environment values, origins, runtimes, and service configuration are set.

No deployment, service creation, code change, migration, database change, secret change, commit, or push was performed. Hosted Supabase and production platform state were not accessed.

Classification summary:

| Classification | Count | Meaning in this audit |
|---|---:|---|
| `READY` | 18 | Repository evidence supports deployment as-is for this item. |
| `NEEDS CONFIGURATION` | 22 | A platform value, environment variable, origin, runtime, or operational setting must be provided before deployment. |
| `BLOCKED` | 2 | A known defect or release-state issue prevents clean production readiness until resolved. |
| `NOT VERIFIED` | 14 | Requires hosted platform, production secret, or runtime evidence outside this read-only audit. |

The most important pre-deployment requirements are:

1. Set all required Render backend environment variables, including Django secret key, database URL, allowed hosts, CORS origin, and Supabase/authentication settings.
2. Set all required Vercel frontend environment variables and keep development login disabled.
3. Use the public HTTPS Render API origin in the frontend API base URL.
4. Pin `PYTHON_VERSION=3.14.10` on Render and set the Vercel Node.js Version to `24.x`.
5. Resolve the known oversized-request-notes defect before treating the deployment as production-ready.

## 2. Scope and method

### 2.1 In scope

- Repository evidence for the Django backend under `backend/`.
- Repository evidence for the Next.js frontend under `frontend/`.
- Existing deployment, production-readiness, E2E, and defect-review documents under `docs/`.
- Existing Supabase migration files as repository evidence only.
- Public platform documentation for Render and Vercel.
- Exact dashboard configuration recommendations for Render and Vercel.

### 2.2 Out of scope

- Creating or modifying Vercel or Render services.
- Running `vercel`, `render`, `git push`, deployment pipelines, or migrations.
- Deploying code or performing smoke tests against live URLs.
- Reading or changing hosted Supabase configuration, users, RLS policies, secrets, database data, or logs.
- Viewing existing production environment variable values.
- Modifying source code, environment files, secrets, dependencies, lockfiles, or documentation other than this report.

### 2.3 Evidence sources

Primary repository evidence reviewed:

- `backend/config/settings.py`
- `backend/config/urls.py`
- `backend/config/wsgi.py`
- `backend/config/health.py`
- `backend/requirements.txt`
- `backend/.env.example`
- `backend/authentication/dev_login.py`
- `backend/authentication/jwt.py`
- `backend/authentication/middleware.py`
- `backend/common/errors.py`
- `backend/requests_app/serializers.py`
- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/next.config.ts`
- `frontend/lib/api.ts`
- `frontend/lib/supabase.ts`
- `frontend/app/requests/new/page.tsx`
- `frontend/.env.example`
- `.gitignore`
- `README.md`
- `docs/B-06B_E2E_TEST_REPORT.md`
- `docs/B-07A_DEFECT_REVIEW_REPORT.md`
- `docs/PRODUCTION_READINESS_REPORT.md`
- `docs/SUPABASE_SETUP.md`
- `supabase/migrations/*.sql`

Public documentation retrieved:

- Render supported languages and Python version documentation.
- Render Django, health check, monorepo/root directory, and environment-variable documentation.
- Vercel Next.js, Node.js runtime/version, build configuration, environment, environment-variable, and project documentation.
- Next.js 16 upgrade documentation bundled/referenced during this audit.

Documentation URLs that were unavailable or returned 404 during the audit were not used as evidence.

### 2.4 Classification definitions

| Label | Definition used here |
|---|---|
| `READY` | Required repository evidence exists and no deployment-specific action is needed for the item. |
| `NEEDS CONFIGURATION` | The application supports the item, but a required platform setting, environment value, origin, secret, or runtime selection must be supplied. |
| `BLOCKED` | A confirmed defect or missing prerequisite prevents a clean production deployment/readiness sign-off. |
| `NOT VERIFIED` | The item depends on hosted service state, production values, live network behavior, or platform account configuration that this audit did not access. |

## 3. Classification matrix

### 3.1 Backend: Render/Django

| ID | Audited item | Classification | Evidence and required action |
|---|---|---|---|
| B-01 | Repository root / monorepo path | `READY` | Backend source is under `backend/`. The Django project package is `backend/config/`. Render supports setting a service root directory for monorepos. Configure Render Root Directory as `backend`. |
| B-02 | WSGI application entry point | `READY` | `config/wsgi.py` exposes the standard Django application object. Use `config.wsgi:application` as the Gunicorn target. |
| B-03 | Python dependency manifest | `READY` | `backend/requirements.txt` exists and pins Django, Gunicorn, PostgreSQL/Supabase-related libraries, JWT handling, CORS, and environment loading dependencies. |
| B-04 | Build command | `READY` | The repository has no Render build script. A conventional Python build command can install the manifest directly: `python -m pip install -r requirements.txt`. |
| B-05 | Start command | `READY` | Gunicorn is a pinned dependency and the WSGI target is present. Use the Render-provided `$PORT`. |
| B-06 | Health check endpoint | `READY` | `config/urls.py` maps `/health` to `config.health.HealthView`, which returns an unauthenticated OK response. Configure Render Health Check Path as `/health`. |
| B-07 | Python runtime version | `NEEDS CONFIGURATION` | No `runtime.txt`, `.python-version`, or equivalent backend runtime pin exists. Requirements/README evidence references Python 3.14 and Django 6.1.3. Render documentation states `PYTHON_VERSION` or `.python-version` controls the version and that services created before 2026-11-03 may have a different default. Set `PYTHON_VERSION=3.14.10` before deployment. |
| B-08 | Linux runtime verification | `NOT VERIFIED` | Audit evidence is Windows-based. The startup command is conventional, but Linux behavior on Render was not executed. Confirm during the first controlled deployment/build validation. |
| B-09 | Django secret key | `NEEDS CONFIGURATION` | `settings.py` requires `DJANGO_SECRET_KEY` when `DJANGO_DEBUG` is false. Set a strong secret in Render; do not commit it. |
| B-10 | Debug mode | `NEEDS CONFIGURATION` | `DJANGO_DEBUG` defaults to false in code, but the production value must be explicitly confirmed in Render. Set `DJANGO_DEBUG=false`. |
| B-11 | Allowed hosts | `NEEDS CONFIGURATION` | `DJANGO_ALLOWED_HOSTS` defaults to local values. Set it to the Render service hostname and any custom API hostname, without URL scheme. Include `.onrender.com` host form only if it is the intended hostname pattern; exact hostnames are preferred when known. |
| B-12 | CORS origins | `NEEDS CONFIGURATION` | `CORS_ALLOWED_ORIGINS` defaults to `http://localhost:3000`. Set it to the exact HTTPS Vercel production origin (and staging origin if used). Do not use a wildcard for this authenticated application. |
| B-13 | Database connection | `NEEDS CONFIGURATION` | `settings.py` requires `DATABASE_URL` when debug is false. Supply the hosted PostgreSQL/Supabase connection URL as a Render secret environment variable. Do not place it in source or frontend configuration. |
| B-14 | Test database variable | `NEEDS CONFIGURATION` | `TEST_DATABASE_URL` is only allowed when `DJANGO_DEBUG=true`. Leave it unset in production; never point it at the production database. |
| B-15 | Django static files | `NOT VERIFIED` | Render's generic Django guide discusses static-file serving, but this API-focused repository has no evidence that static file collection is required by the deployed service. Confirm whether `collectstatic`/WhiteNoise is needed; do not add dependencies or settings during this read-only audit. |
| B-16 | Database migrations on deploy | `NOT VERIFIED` | Migration SQL exists under `supabase/migrations/`, but no Render deploy-time migration command was found and hosted migration state was not accessed. Decide whether migrations are completed outside deployment or by an approved release step before go-live. |
| B-17 | Supabase JWT verification settings | `NEEDS CONFIGURATION` | The verifier supports HS256, RS256, and ES256 and checks signature, algorithm, issuer, audience, expiry, and required claims. Set `SUPABASE_URL` and either `SUPABASE_JWKS_URL` for asymmetric keys or `SUPABASE_JWT_SECRET` for legacy HS256. Keep `SUPABASE_JWT_ISSUER` and `SUPABASE_JWT_AUDIENCE` unset unless overriding defaults is required. |
| B-18 | JWT audience/issuer values | `NEEDS CONFIGURATION` | Defaults are treated as Supabase issuer path `/auth/v1` and audience `authenticated`. Confirm these values for the target Supabase project; set explicit overrides only if the project uses non-default values. |
| B-19 | Development login endpoint | `NEEDS CONFIGURATION` | `DevLoginView` exists at `/api/auth/dev-login/`, but it rejects requests unless Django debug is true. Keep `DJANGO_DEBUG=false` and verify the production endpoint denies access in a controlled post-deployment check. |
| B-20 | Authorization role source | `READY` | JWT verification code and prior review evidence show roles are resolved from `public.profiles`, not trusted from JWT role claims. This reduces privilege-escalation risk from client-supplied claims. |
| B-21 | Error response safety | `READY` | `common/errors.py` returns a generic internal-error envelope for unhandled exceptions, and reviewed authentication errors are sanitized. Do not enable Django debug or verbose exception output in production. |
| B-22 | Render plan / scaling / instances | `NOT VERIFIED` | No account, plan, region, instance count, autoscaling, or custom domain state was accessed. Select and verify these in the Render dashboard according to availability and cost requirements. |

### 3.2 Frontend: Vercel/Next.js

| ID | Audited item | Classification | Evidence and required action |
|---|---|---|---|
| F-01 | Repository root | `READY` | Frontend source is under `frontend/`. Configure Vercel Root Directory as `frontend`. |
| F-02 | Framework preset | `READY` | `frontend/package.json` declares Next.js. Select the Vercel Next.js framework preset. |
| F-03 | Package manager / lockfile | `READY` | `package-lock.json` is present and uses lockfile version 3. Use `npm ci` so the lockfile is honored. |
| F-04 | Build script | `READY` | `package.json` provides `npm run build`. Use it as the Vercel Build Command. |
| F-05 | Install command | `READY` | The repository has no root-level install wrapper. Use `npm ci`. |
| F-06 | Next.js configuration | `READY` | `next.config.ts` is minimal and enables React strict mode. No repository evidence requires a custom build output setting for Vercel. |
| F-07 | Node.js runtime | `NEEDS CONFIGURATION` | No `engines`, `.nvmrc`, or `.node-version` exists in `frontend/`. Bundled Next.js package metadata requires Node `>=20.9.0`. Vercel currently exposes `26.x`, `24.x`, and `22.x`; all meet that minimum. Set Vercel Node.js Version to `24.x` for a supported, reproducible LTS runtime. |
| F-08 | Production API base URL | `NEEDS CONFIGURATION` | `lib/api.ts` falls back to `http://127.0.0.1:8000`, which is not valid for a hosted frontend. Set `NEXT_PUBLIC_API_BASE_URL` to the HTTPS Render API origin, with no trailing slash. |
| F-09 | Supabase URL | `NEEDS CONFIGURATION` | `lib/supabase.ts` falls back to a local URL. Set `NEXT_PUBLIC_SUPABASE_URL` to the target hosted Supabase project URL. |
| F-10 | Supabase public key | `NEEDS CONFIGURATION` | The frontend supports `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` or `NEXT_PUBLIC_SUPABASE_ANON_KEY`. Set one to the correct public/publishable key for the target project. Do not use a secret key. |
| F-11 | Development login switch | `NEEDS CONFIGURATION` | `NEXT_PUBLIC_ALLOW_DEV_LOGIN` enables local-only login UI behavior. Set it to `false` or leave it unset for Vercel Production. If used in Preview, restrict it to non-production origins. |
| F-12 | Hardcoded local fallbacks | `NEEDS CONFIGURATION` | Frontend helpers contain local API/Supabase fallbacks and a local placeholder key marker. They are useful for offline development but must not be relied on in production. Explicit Vercel environment variables override them. |
| F-13 | Secret exposure boundary | `NEEDS CONFIGURATION` | Only public Supabase URL/key values and public API origin belong in `NEXT_PUBLIC_*` variables. Do not add database URLs, JWT secrets, privileged Supabase keys, or secret API keys to Vercel frontend variables. |
| F-14 | Environment scope | `NEEDS CONFIGURATION` | Vercel supports separate Production and Preview environments. Set the Production values explicitly and decide whether Preview uses the same hosted backend or a staging backend. Do not let Preview point to production data without approval. |
| F-15 | Commit state used for deployment | `BLOCKED` | Initial git status showed untracked backend artifact `backend/b05b7_r.py` and untracked reports. A Git-based Vercel/Render deployment builds committed state, not arbitrary local untracked files. Review and commit or intentionally exclude the intended source before creating a deployment. |
| F-16 | Vercel project / domain / plan state | `NOT VERIFIED` | No Vercel account, project, domain, deployment settings, or plan state was accessed. Verify in the Vercel dashboard. |
| F-17 | Production build result | `NOT VERIFIED` | The repository has scripts and dependencies, but no Vercel Production build was executed. Confirm after configuration in a controlled deployment. |
| F-18 | Browser workflow tests F1–F4 | `NOT VERIFIED` | `docs/B-06B_E2E_TEST_REPORT.md` records four frontend workflow tests as BLOCKED because no approved browser/E2E driver was available. This audit did not add a driver or rerun them. |
| F-19 | Hosted auth redirect configuration | `NOT VERIFIED` | Password recovery and authentication redirects depend on hosted Supabase and production URL configuration, neither of which was accessed. Verify after the production frontend origin is fixed. |

### 3.3 Database, security, and operations

| ID | Audited item | Classification | Evidence and required action |
|---|---|---|---|
| D-01 | Repository-level RLS migrations | `READY` | Supabase migration files exist and include RLS, grants, function search-path hardening, and related fixes. This is repository evidence only. |
| D-02 | Hosted RLS enforcement | `NOT VERIFIED` | Hosted Supabase state was not accessed. Confirm migrations are applied and policies are active in the target project before exposing production traffic. |
| D-03 | Live Supabase Auth | `NOT VERIFIED` | Login, token issuance, recovery, and user state require the hosted project. Do not treat local development login as proof of production Auth. |
| D-04 | Live JWKS/RS256 verification | `NOT VERIFIED` | The backend code supports asymmetric verification, but no live JWKS fetch or production token validation was performed. Verify in staging or a controlled deployment window. |
| D-05 | Production environment variable values | `NOT VERIFIED` | Variable names and requirements were reviewed; values were not. No secret values were read, copied, or reproduced. |
| D-06 | Database compatibility/migration history | `NOT VERIFIED` | The repository contains migration SQL, but hosted schema version and successful application history were not inspected. |
| D-07 | `.gitignore` handling of secrets | `READY` | `.gitignore` excludes environment/secret material while preserving example files. Keep all real credentials out of source control. |
| D-08 | Known defect DR-01 / BUG-1 | `BLOCKED` | `docs/B-07A_DEFECT_REVIEW_REPORT.md` confirms oversized request notes bypass serializer-level length validation, hit the database 1000-character check, and return `500/internal_error`. Resolve before production readiness sign-off. |
| D-09 | Other B-07A findings | `READY` | The defect review identified no Critical or High findings and classified most other items as product decisions, test limitations, or acceptable behavior. |
| D-10 | A10 hospital-user authorization check | `NOT VERIFIED` | B-06B marks A10 `NOT TESTED` because no endpoint uses `IsHospitalUser`. Confirm whether that permission class is intentionally unused or whether a test/endpoint gap must be addressed. |
| D-11 | Existing production readiness status | `READY` | `docs/PRODUCTION_READINESS_REPORT.md` states local acceptance PASS and production acceptance PENDING / NOT READY. This audit preserves that conclusion rather than overriding it. |
| D-12 | No platform artifacts | `NEEDS CONFIGURATION` | No `render.yaml`, `vercel.json`, `Procfile`, `runtime.txt`, `.nvmrc`, or `.node-version` exists. Dashboard-only deployment is possible, but infrastructure-as-code and runtime pinning are absent. Add or configure these only through an approved change process. |
| D-13 | Repository cleanliness for release | `NEEDS CONFIGURATION` | The initial status contained untracked files. Before deployment, confirm the intended branch and commit contain exactly the source and reports that should be released. |
| D-14 | Rollback/backup plan | `NEEDS CONFIGURATION` | No rollback or backup procedure was found in the audited deployment evidence. Define an owner, rollback target, and data backup/check approach before production traffic. |
| D-15 | Post-deployment smoke checks | `NEEDS CONFIGURATION` | Define controlled checks for `/health`, frontend load, one authenticated API call, CORS preflight, dev-login denial, and error-envelope behavior. Do not run them during this read-only audit. |

## 4. Exact Render configuration recommendations

These are dashboard recommendations only. No service was created or changed.

### 4.1 Render web service

| Setting | Exact value |
|---|---|
| Service type | Web Service |
| Environment | Python |
| Region | Choose the region required by project policy and latency/data-residency requirements |
| Branch | Approved deployment branch after the working tree is reviewed and intended changes are committed |
| Root Directory | `backend` |
| Build Command | `python -m pip install -r requirements.txt` |
| Start Command | `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT` |
| Health Check Path | `/health` |
| Python version | `3.14.10` (set `PYTHON_VERSION=3.14.10`; do not rely on the service default) |
| Auto Deploy | Enable only after the deployment branch and commit state are approved |
| Instance/plan | Select according to approved capacity and availability requirements |

Render documentation confirms Python service support, `PYTHON_VERSION`/.python-version control, root-directory support for monorepos, and HTTP health-check paths for web services.

### 4.2 Render environment variables

Set these as Render service environment variables/secret values. Names are exact; values must be supplied by an authorized owner and are deliberately not reproduced here.

| Variable | Required production value or rule |
|---|---|
| `DJANGO_SECRET_KEY` | Strong random Django secret. Keep secret. |
| `DJANGO_DEBUG` | `false` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated exact Render/custom API hostnames, no scheme. Example shape: `api-host.onrender.com,custom-api.example.com` |
| `CORS_ALLOWED_ORIGINS` | Exact HTTPS frontend origin(s), no trailing slash. Example shape: `https://frontend.example.com` |
| `DATABASE_URL` | Hosted PostgreSQL/Supabase connection URL supplied as a secret. Keep secret. |
| `SUPABASE_URL` | Target hosted Supabase project URL. |
| `SUPABASE_JWKS_URL` | Set when using asymmetric RS256/ES256 tokens; often can be derived from `SUPABASE_URL`, but set explicitly if required by the target project. |
| `SUPABASE_JWT_SECRET` | Set only for legacy HS256 tokens. Leave unset when using JWKS/asymmetric keys. Keep secret. |
| `SUPABASE_JWT_ISSUER` | Leave unset unless the target project uses a non-default issuer. |
| `SUPABASE_JWT_AUDIENCE` | Leave unset unless the target project uses a non-default audience. |
| `TEST_DATABASE_URL` | Leave unset in production. |
| `PYTHON_VERSION` | `3.14.10` |
| `PORT` | Do not set manually; Render supplies it for the Start Command. |

Security rule: never place privileged Supabase keys, secret API keys, database URLs, or JWT secrets in frontend/Vercel configuration.

### 4.3 Render migration/release decision

Repository evidence does not show a deploy-time Django migration command, and hosted migration state was not accessed. Before go-live, an authorized owner must choose one of these approaches:

1. Apply reviewed Supabase migrations to the target database through the approved existing release process, and verify the applied version; or
2. Add an explicit release step after a separate review and validation.

This report does not recommend silently adding migrations to the web service start command.

## 5. Exact Vercel configuration recommendations

These are dashboard recommendations only. No project, deployment, domain, environment, or setting was created or changed.

### 5.1 Vercel project

| Setting | Exact value |
|---|---|
| Import source | Approved Git repository and branch |
| Root Directory | `frontend` |
| Framework Preset | Next.js |
| Node.js Version | `24.x` (satisfies the bundled Next.js minimum of `>=20.9.0`) |
| Install Command | `npm ci` |
| Build Command | `npm run build` |
| Output Directory | Leave framework default; do not override based on current repo evidence |
| Environment scope | Set explicit Production values; define Preview values deliberately |
| Auto Deploy | Enable only after the deployment branch and commit state are approved |

### 5.2 Vercel Production environment variables

Set these as Vercel Production environment variables. Values must be supplied by an authorized owner and are deliberately not reproduced here.

| Variable | Required production value or rule |
|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | Exact HTTPS Render API origin with no trailing slash. Example shape: `https://api.example.com` |
| `NEXT_PUBLIC_SUPABASE_URL` | Target hosted Supabase project URL. |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | Correct public/publishable key for the target Supabase project. Use this preferred name when available. |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Alternative supported name for the public anon/publishable key. Use one supported key name consistently; do not add a secret key. |
| `NEXT_PUBLIC_ALLOW_DEV_LOGIN` | `false` or unset in Production. If present, use the literal lowercase string `false`. |

Vercel documentation confirms separate Production/Preview environments and encrypted/secret variable handling. Because these variables use the `NEXT_PUBLIC_` prefix, they are exposed to browser code; only public values are permitted.

### 5.3 Vercel Preview environment

Recommended rule:

- Use the same frontend build settings as Production.
- Point Preview at a staging API and staging Supabase project when available.
- If Preview must use the production backend, require explicit approval because browser workflows can mutate registry data.
- Keep `NEXT_PUBLIC_ALLOW_DEV_LOGIN` disabled unless the Preview is intentionally isolated and non-production.

## 6. Pre-deployment gate

Deployment should not be treated as production-ready until all of the following are true:

1. **Configuration complete:** Every Render and Vercel variable in Sections 4.2 and 5.2 has an approved value.
2. **Runtime pinned:** Render Python and Vercel Node.js versions are explicitly selected and compatible with the pinned dependencies.
3. **Origins aligned:** Render `DJANGO_ALLOWED_HOSTS` and `CORS_ALLOWED_ORIGINS` match the actual Vercel origin and Render API host.
4. **Development login disabled:** `DJANGO_DEBUG=false` and `NEXT_PUBLIC_ALLOW_DEV_LOGIN` is `false`/unset.
5. **Hosted database verified:** Target database exists, credentials work, and the intended migration state is applied.
6. **Hosted auth verified:** Supabase URL/key/JWKS or JWT settings are correct, and redirects use the production frontend origin.
7. **Known defect resolved or accepted:** DR-01/BUG-1 is fixed and regression-tested before production sign-off. If accepted as a temporary risk, document the owner and follow-up date; this report does not accept it.
8. **Commit state approved:** Intended source is committed to the deployment branch; untracked/local-only artifacts are reviewed.
9. **Controlled smoke checks completed:** `/health`, frontend load, authenticated API call, CORS, dev-login denial, and error envelope behavior are checked after deployment by an authorized operator.
10. **Rollback plan recorded:** Owner, prior known-good revision, data considerations, and rollback steps are documented.

## 7. Items intentionally left unverified

The following remain `NOT VERIFIED` because verification would require production access, live traffic, secret values, or platform action prohibited by this audit:

- Hosted Supabase Auth behavior.
- Live JWKS/RS256 token verification.
- Password recovery and redirect behavior.
- Hosted RLS policy application and enforcement.
- Actual production environment variable values.
- Render Linux runtime behavior.
- Render plan, region, custom domain, scaling, and instance state.
- Vercel project, domain, plan, build result, and deployment state.
- Applied database schema/migration history.
- Static-file requirement for the API service.
- A10 authorization behavior and whether `IsHospitalUser` is intentionally unused.
- Browser workflow tests F1–F4.

## 8. Audit safeguards and final state

No secrets, passwords, tokens, database URLs, UUIDs, email addresses, or phone numbers were copied into this report. Example values use generic placeholders or shapes only.

The following were not performed:

- No Vercel project or deployment was created.
- No Render service or database was created.
- No hosted Supabase resource was read or modified.
- No code, environment file, secret, database, or migration was modified.
- No migration was applied.
- No commit or push was made.
- No live production smoke test was run.

Final classification: **NEEDS CONFIGURATION**, with two `BLOCKED` items (DR-01/BUG-1 and the unreviewed release commit state) that must be resolved before an unqualified production-ready decision.
