# D-02B — Django Production Security Configuration Plan

Date: 2026-11-23
Task type: read-only security configuration planning
Scope: Django backend security settings for Render deployment
Status: PLAN ONLY — no implementation performed

## 1. Restrictions observed

- No source file was modified.
- No environment file was modified or read for secret values.
- No hosted database, Supabase project, Render service, or deployment was accessed.
- No migration was run and no service was created.
- No credential, token, database URL, UUID, email address, phone number, or secret value is reproduced in this report.
- All existing untracked files remain preserved.

## 2. Current configuration findings

| Area | Current implementation | Assessment |
|---|---|---|
| Middleware order | `CorsMiddleware`, `CommonMiddleware`, `SupabaseClaimsMiddleware` | CORS is before response-generating middleware, which is correct. `django.middleware.security.SecurityMiddleware` is absent. No `SessionMiddleware`, `AuthenticationMiddleware`, or `CsrfViewMiddleware` is present. |
| `DEBUG` | `DJANGO_DEBUG` from environment; defaults to `false` | Correct production default. Debug enables development fallbacks when true and must stay false in production. |
| `ALLOWED_HOSTS` | Parsed from `DJANGO_ALLOWED_HOSTS`; defaults to local hosts | Safe default locally, but production hosts must be set explicitly. No automatic Render hostname handling exists. |
| `CSRF_TRUSTED_ORIGINS` | Not configured | Currently inert because there is no `CsrfViewMiddleware` and no session/cookie authentication. Should still be aligned with CORS for defense in depth. |
| `SECURE_SSL_REDIRECT` | Not configured; Django default is `False` | No application-level HTTP-to-HTTPS redirect. HTTPS enforcement must be handled by Render initially. |
| `SECURE_PROXY_SSL_HEADER` | Not configured; Django default is `None` | Django does not currently trust forwarded HTTPS headers. Required only if application-level secure detection is enabled. |
| `SESSION_COOKIE_SECURE` | Not configured; Django default is `False` | No cookie sessions are used, but production should set it to `True` as defense in depth. |
| `CSRF_COOKIE_SECURE` | Not configured; Django default is `False` | No CSRF cookie workflow is used, but production should set it to `True` as defense in depth. |
| HSTS | Not configured; defaults are max-age `0`, `includeSubDomains=False`, `preload=False` | No HSTS header is sent. A staged rollout is required. |
| Other Django defaults | `SECURE_CONTENT_TYPE_NOSNIFF=True`, `SECURE_REFERRER_POLICY='same-origin'`, `SECURE_CROSS_ORIGIN_OPENER_POLICY='same-origin'`, `X_FRAME_OPTIONS='DENY'` | Good defaults, but currently not applied because `SecurityMiddleware` is absent, except headers emitted elsewhere. Make them explicit in settings. |
| CORS | `CORS_ALLOWED_ORIGINS` from environment; defaults to local frontend; `CORS_ALLOW_CREDENTIALS=False` | Correct model: exact allowlist, no credentials. Default headers include `authorization` and `content-type`, and default methods include `PATCH`, so the frontend Bearer-token API calls are supported. |
| `/health` | `path("health", HealthView.as_view())`; unauthenticated, no DB query, returns `{"status": "ok"}` | Correct liveness endpoint. It is still subject to `ALLOWED_HOSTS` and currently emits no security headers. |
| Authentication | DRF uses only `SupabaseJWTAuthentication`; JWT in `Authorization` header | No cookie/CSRF dependency. Supabase JWT verification and RLS claim propagation are unaffected by cookie settings. |

## 3. Recommended production configuration

### 3.1 Debug and secret handling

| Setting | Recommendation | Rationale |
|---|---|---|
| `DJANGO_DEBUG=false` | Required in Render | Preserves the existing guards: secret key required, test database fallback disabled, development login denied, verbose auth logs reduced. |
| `DJANGO_SECRET_KEY` | Strong random secret in Render only | Already required by settings when debug is false. Never store in source. |

### 3.2 Host validation

Keep `ALLOWED_HOSTS` explicit and environment-driven. Do not use `*`.

Recommended behavior in `backend/config/settings.py`:

- Parse `DJANGO_ALLOWED_HOSTS` exactly as today.
- Optionally append Render's automatically supplied `RENDER_EXTERNAL_HOSTNAME` when present.
- Still require any verified custom API hostname to be listed in `DJANGO_ALLOWED_HOSTS`, because Render health checks may use a custom domain as the `Host` header.

This preserves local development because `RENDER_EXTERNAL_HOSTNAME` is absent locally.

### 3.3 HTTPS termination and forwarded HTTPS handling

Recommended order of decisions:

1. Keep HTTPS enforcement at Render first. Render terminates TLS and can redirect HTTP to HTTPS at the platform layer.
2. Keep `SECURE_SSL_REDIRECT=False` initially. This avoids redirect loops when Django cannot see the original HTTPS scheme behind the proxy.
3. Do **not** set `SECURE_PROXY_SSL_HEADER` until it is confirmed that Render sends `X-Forwarded-Proto: https` for HTTPS requests **and** strips or overwrites client-supplied values. Trusting an unvalidated forwarded header would allow a client to spoof `request.is_secure()`.
4. If `SECURE_PROXY_SSL_HEADER` is later verified and enabled, use:

   ```python
   SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
   ```

5. If application-level redirect is later enabled, also add:

   ```python
   SECURE_REDIRECT_EXEMPT = [r"^health$"]
   ```

   This keeps the Render probe from receiving a 301. The health response is non-sensitive, so exempting it from redirect does not expose data.

Preferred end state: Render performs the HTTPS redirect; Django uses `SECURE_PROXY_SSL_HEADER` only for correct scheme awareness if needed, and `SECURE_SSL_REDIRECT` remains `False`.

### 3.4 Security middleware placement

Add `django.middleware.security.SecurityMiddleware` to `MIDDLEWARE`, immediately after `CorsMiddleware`:

```python
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "authentication.middleware.SupabaseClaimsMiddleware",
]
```

Rationale:

- `CorsMiddleware` must stay before middleware that can generate responses so CORS headers are added to error and redirect responses.
- With `SECURE_SSL_REDIRECT=False`, `SecurityMiddleware` does not generate redirects, so placing it after `CorsMiddleware` is safe.
- `SecurityMiddleware` remains before the Supabase claims middleware, which opens the database transaction.
- If application-level SSL redirect is ever enabled, re-test CORS preflight ordering and health-check behavior before release.

### 3.5 Secure cookies and CSRF trusted origins

Recommended settings:

```python
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
CSRF_TRUSTED_ORIGINS = list(CORS_ALLOWED_ORIGINS)
```

Rationale:

- The API uses Bearer tokens and has no session or CSRF cookie flow, so these settings do not break current clients.
- In production they ensure any future Django session/CSRF cookies are HTTPS-only.
- Locally they remain false, preserving offline development.
- Deriving `CSRF_TRUSTED_ORIGINS` from `CORS_ALLOWED_ORIGINS` keeps the exact origin list consistent if CSRF protection is added later. It is inert today.
- Keep `CORS_ALLOW_CREDENTIALS=False`; the frontend sends `Authorization` explicitly and does not rely on cookies.

### 3.6 HSTS rollout

Recommended staged values:

| Stage | `SECURE_HSTS_SECONDS` | `SECURE_HSTS_INCLUDE_SUBDOMAINS` | `SECURE_HSTS_PRELOAD` | Action |
|---|---:|---|---|---|
| 1 | `0` | `False` | `False` | Add middleware; no HSTS header yet. |
| 2 | `300` | `False` | `False` | Short production trial; verify header appears only on HTTPS. |
| 3 | `86400` | `False` | `False` | One-day max-age after clean trial. |
| 4 | `31536000` | `False` | `False` | One-year max-age after sustained clean operation. |

`includeSubDomains` and `preload` must remain `False` unless a separate review confirms:

- Every subdomain of the registrable domain is HTTPS-only and controlled by the project.
- No legacy HTTP-only subdomain exists.
- For `preload`, the one-year max-age and `includeSubDomains` requirements are met and an explicit browser preload-list submission is intended. Preload is difficult to reverse and can break unrelated subdomains.

### 3.7 CORS origin

The repository does not contain a production frontend origin; only local placeholders and documentation examples exist. Therefore the exact production value must be supplied by the authorized owner after the Vercel project/domain is fixed.

Recommended value:

- `CORS_ALLOWED_ORIGINS` = exactly the canonical Vercel Production origin, for example the single HTTPS origin `https://<final-frontend-host>`.
- No trailing slash, no path, no port unless non-standard, no wildcard, no `http://localhost:3000` in production.
- If both apex and `www` are verified production origins, list both exactly.
- Keep preview/staging origins in a separate environment; do not merge them into the Production value without approval.

Default `CORS_ALLOW_HEADERS` already permits `authorization` and `content-type`, and default `CORS_ALLOW_METHODS` already permits `PATCH`, so no custom CORS header/method lists are required for the current frontend.

### 3.8 Health-check compatibility

- Keep the route at `/health` with no trailing slash.
- Keep `HealthView` unauthenticated and database-free.
- Ensure `DJANGO_ALLOWED_HOSTS` includes the hostname Render uses for probes.
- Keep `SECURE_SSL_REDIRECT=False` initially; if enabled later, exempt `^health$`.
- HSTS and response security headers do not change the 200 status and are safe for the probe.

## 4. Exact files that would require modification

| File | Change required | Notes |
|---|---|---|
| `backend/config/settings.py` | Yes | Primary change: middleware order, explicit security settings, optional Render hostname handling, HSTS staging values, CSRF trusted origins. |
| `backend/config/tests/test_settings.py` or a new `backend/config/tests/test_security.py` | Recommended | Add regression tests for local defaults, production values, host handling, CORS/CSRF alignment, and health exemptions. |
| `backend/config/urls.py` | No | Route is already correct. |
| `backend/config/health.py` | No | View is already correct. |
| `backend/config/wsgi.py` | No | Entry point is already correct. |
| `backend/requirements.txt` | No | `django-cors-headers` is already present; no new dependency is needed. |
| Frontend source or env example files | No | The frontend already sends Bearer tokens via `Authorization`; only deployed env values change. |
| Supabase migrations or policies | No | These settings do not affect database RLS or grants. |
| `.env` files | No | Real values belong only in Render dashboard variables. |

A future `render.yaml` could encode the service, but that is a separate infrastructure-as-code decision and is not required for this plan.

## 5. Required Render environment variables

Existing required variables:

| Variable | Rule |
|---|---|
| `DJANGO_DEBUG` | `false` |
| `DJANGO_SECRET_KEY` | Strong secret; keep in Render only |
| `DJANGO_ALLOWED_HOSTS` | Exact API hostnames used by Render probes and clients; no scheme |
| `DATABASE_URL` | Hosted database URL as a Render secret; least-privilege, RLS-bound role |
| `CORS_ALLOWED_ORIGINS` | Exact canonical frontend HTTPS origin |
| `SUPABASE_URL` | Correct hosted project URL |
| `SUPABASE_JWKS_URL` or `SUPABASE_JWT_SECRET` | Exactly one strategy appropriate for the project |
| `SUPABASE_JWT_ISSUER` | Explicit value only if non-default |
| `SUPABASE_JWT_AUDIENCE` | Usually `authenticated`; override only if confirmed |
| `PYTHON_VERSION` | `3.14.10` |
| `RENDER_EXTERNAL_HOSTNAME` | Supplied automatically by Render; do not set manually |

Variables to leave unset in production:

| Variable | Rule |
|---|---|
| `TEST_DATABASE_URL` | Must be unset; debug=false already prevents fallback |
| `PORT` | Supplied by Render |

Optional variables if the chosen design makes HSTS stage values runtime-configurable:

| Variable | Rule |
|---|---|
| `DJANGO_SECURE_HSTS_SECONDS` | Stage value only; default to `0` in code |
| `DJANGO_SECURE_SSL_REDIRECT` | Prefer unset/false; only use after verified proxy handling |

`SECURE_PROXY_SSL_HEADER` is recommended as a literal in settings after verification rather than an environment variable, because its tuple format is easy to misconfigure as a string.

## 6. Compatibility verification

| Concern | Why the plan is compatible | Validation required |
|---|---|---|
| Local development | `RENDER_EXTERNAL_HOSTNAME` is absent; `DEBUG=true` keeps cookie secure flags off, HSTS at zero, redirect off, local `ALLOWED_HOSTS` and CORS defaults intact. | Run local backend suite and local `/health` check after the change. |
| Supabase authentication | JWT is sent in the `Authorization` header; no cookies, sessions, or CSRF token are used. JWT verification, issuer/audience checks, and claims middleware are unchanged. | Run an authenticated API request from the allowed origin; confirm expected 200/401/403 behavior. |
| Vercel frontend requests | Exact origin allowlist; credentials are not used; default CORS headers/methods cover `Authorization`, `Content-Type`, and `PATCH`. | Browser preflight and real API call from the final frontend origin. |
| Render health checks | Correct path and status; host must be allowed; redirect remains off initially and can be exempted later. | Confirm 200 from Render probe after each stage. |
| Database RLS | No database, model, view, migration, or policy change; `SupabaseClaimsMiddleware` remains in place and transaction-scoped. | Existing RLS/auth tests plus one controlled live request after deployment. |
| JWT verification | No verifier settings are changed; only transport/security headers and cookie flags change. | Existing auth tests and live JWKS token validation in an approved window. |

## 7. Risks and validation tests

| Risk | Mitigation | Test |
|---|---|---|
| Health check fails with 400 | Include probe host in `DJANGO_ALLOWED_HOSTS` | Request `/health` with the exact Render host; expect 200. Request with unknown host; expect 400. |
| Redirect loop behind TLS terminator | Keep `SECURE_SSL_REDIRECT=False`; only set proxy header after verification | HTTPS request returns 200 with no redirect loop. If enabled later, verify `SECURE_REDIRECT_EXEMPT` keeps `/health` at 200. |
| Spoofed forwarded protocol | Only trust `X-Forwarded-Proto` if the proxy strips/overwrites client headers | Confirm proxy behavior in staging; send a spoofed header directly to the origin and verify it is not trusted. |
| Vercel requests blocked by CORS | Exact origin, no wildcard, credentials false | Preflight `OPTIONS` from allowed origin returns expected `Access-Control-Allow-Origin`; disallowed origin receives no allow-origin header. |
| HSTS breaks HTTP subdomains | Keep `includeSubDomains` and `preload` false; staged max-age | Inspect `Strict-Transport-Security` on HTTPS responses only; confirm absence on HTTP. |
| Cookie flags break local flows | Gate with `not DEBUG` | Local development login and API calls still work with `DEBUG=true`. |
| Debug login exposed | `DJANGO_DEBUG=false` in Render | POST to dev-login returns denial in production-like environment. |
| Security headers missing | Add `SecurityMiddleware` | Response includes `X-Content-Type-Options`, `Referrer-Policy`, `Cross-Origin-Opener-Policy`, and `X-Frame-Options` as configured. |
| Existing behavior regresses | Full regression suite | Run `python manage.py test` and `python manage.py check --deploy` with production-like environment values. |

## 8. Staged implementation and verification sequence

### Stage 0 — Platform prerequisites, no code change

1. Set all required Render environment variables from section 5.
2. Confirm Render HTTPS for the service hostname and any custom domain.
3. Confirm `DJANGO_ALLOWED_HOSTS` contains the host used in the health probe.
4. Confirm `CORS_ALLOWED_ORIGINS` equals the exact frontend production origin.
5. Verify `/health` returns 200 and one authenticated API request succeeds.

Exit criterion: the service is reachable over HTTPS, health is green, and CORS works.

### Stage 1 — Add non-redirecting security headers and cookie flags

Files: `backend/config/settings.py`, plus new/updated security tests.

Changes:

- Insert `SecurityMiddleware` after `CorsMiddleware`.
- Set `SESSION_COOKIE_SECURE = not DEBUG` and `CSRF_COOKIE_SECURE = not DEBUG`.
- Set `CSRF_TRUSTED_ORIGINS = list(CORS_ALLOWED_ORIGINS)`.
- Make `SECURE_CONTENT_TYPE_NOSNIFF`, `SECURE_REFERRER_POLICY`, `SECURE_CROSS_ORIGIN_OPENER_POLICY`, and `X_FRAME_OPTIONS` explicit.
- Keep `SECURE_SSL_REDIRECT=False`, `SECURE_PROXY_SSL_HEADER` unset, HSTS `0`.

Verification:

- Local test suite passes.
- `manage.py check --deploy` has no new blocking errors.
- `/health` remains 200 with security headers present and no HSTS header.
- Vercel-origin preflight and authenticated request still succeed.

### Stage 2 — Verify forwarded HTTPS handling, optional

Only if Django needs scheme awareness or application-level redirect:

1. Confirm Render sends `X-Forwarded-Proto: https` and does not allow client-supplied spoofing.
2. Add `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`.
3. Keep `SECURE_SSL_REDIRECT=False`.
4. Verify no redirect loop, health 200, CORS 200, and authenticated API success.

If verification cannot be completed, skip this stage and rely on Render HTTPS termination.

### Stage 3 — HTTPS redirect decision

Preferred: leave `SECURE_SSL_REDIRECT=False` and enforce redirect at Render.

If an authorized owner chooses Django-level redirect:

1. Require Stage 2 verification.
2. Add `SECURE_REDIRECT_EXEMPT = [r"^health$"]`.
3. Set `SECURE_SSL_REDIRECT=True`.
4. Verify HTTP redirects to HTTPS, `/health` stays 200, preflight succeeds, and no loop occurs.

### Stage 4 — HSTS rollout

1. Set `SECURE_HSTS_SECONDS=300`; verify header on HTTPS only.
2. After a clean observation window, set `86400`; verify again.
3. After sustained clean operation, set `31536000`.
4. Keep `SECURE_HSTS_INCLUDE_SUBDOMAINS=False` and `SECURE_HSTS_PRELOAD=False`.
5. Only evaluate `includeSubDomains` or `preload` in a separate security review with explicit owner approval.

## 9. Final statement

This document is a plan only. It does not authorize implementation, deployment, environment changes, or infrastructure changes. Every stage above requires separate approval, code/test changes where applicable, and controlled verification before production traffic is exposed.
