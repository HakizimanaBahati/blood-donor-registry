# Break-it challenge

Try to bypass the registry rules. Each attempt should fail at the **server**, even when the
browser is manipulated. Record the HTTP status and response code for each attempt.

## Attempt 1 — Remove the eligibility badge in the browser

1. Sign in as **Hospital A**.
2. Open an ineligible donor (30 or 89 days since last donation).
3. In DevTools, delete the eligibility element or add CSS that says “Eligible”.
4. Try to attach that donor to a request.

**Expected defence:** `POST /api/requests/` returns `400` with
`error.code = "ineligible_donor"`. The badge is presentation only; Django recalculates
eligibility from `last_donation` using the verified date.

## Attempt 2 — Post an ineligible donor directly

Use the third command in [CURL_TESTS.md](CURL_TESTS.md), or change `donor_id` to
`a0000002-0000-4000-8000-000000000002` in a request you send from the console.

**Expected defence:** `400 ineligible_donor`, including `days_until_eligible`.

## Attempt 3 — Lie about the role

Decode your access token and try changing `role` to `admin`, or add
`"role": "admin"` to a JSON request body. Re-sign the token only if you own the local
development secret.

**Expected defence:** an unsigned/modified token fails signature verification (`401`).
A valid token whose JWT `role` claim says something else is ignored: Django reads the role
from `public.profiles` using the verified `sub` claim. A body field named `role` is never
used for authorization.

## Attempt 4 — Read another hospital’s requests

Sign in as **Hospital A** and request `GET /api/requests/`. Then try a direct URL with a
request UUID belonging to Hospital B, for example
`GET /api/requests/c0000003-0000-4000-8000-000000000003/`.

**Expected defence:** the list contains only Hospital A rows and the detail lookup returns
`404` because the scoped queryset excludes the other hospital’s record.

## Attempt 5 — Call an admin-only endpoint as a hospital user

Send `GET /api/hospitals/` with a hospital token.

**Expected defence:** `403` with `error.code = "permission_denied"`. The frontend also hides
the Hospitals link, but hiding the link is not the security control.

## Attempt 6 — Steal contact details of an ineligible donor

Ask `GET /api/donors/?eligible=false` with a hospital token.

**Expected defence:** ineligible donors have `"phone": null`. Administrators still receive
the phone number because they need to maintain registry records.

## Attempt 7 — Future-dated donation or duplicate phone

- POST a donor with `last_donation` set to tomorrow.
- POST a second donor using an existing phone number.

**Expected defence:** `400 validation_error` with field-specific messages from the DRF
serializer.

## Attempt 8 — Remove the `Authorization` header

Call any `/api/...` endpoint without a bearer token.

**Expected defence:** `401` with `error.code = "authentication_failed"`.

## Scoring

| Result | Meaning |
|---|---|
| Request blocked with the expected status/code | Server control verified |
| UI blocked but direct API call succeeds | **Bug** — client-only security |
| Unexpected `200` or leaked data | **Critical bug** — stop and report using the template |

## Why this works

The trust boundary is the API. The browser is a convenience layer: it formats data,
disables buttons and displays server-generated badges. JWT verification, role resolution,
hospital scoping, field-level privacy and the 90-day rule all live in Django and the
PostgreSQL schema. See [ARCHITECTURE.md](ARCHITECTURE.md) for the request trace.
