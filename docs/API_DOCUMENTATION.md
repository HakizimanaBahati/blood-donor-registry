# REST API documentation

Base URL (local): `http://localhost:8000`

Every protected endpoint requires:

```
Authorization: Bearer <Supabase access token>
```

The token's signature, algorithm (`HS256` / `RS256` / `ES256`), issuer, audience and
expiry are verified by Django. The application role is read from `public.profiles`
using the verified `sub` claim — role claims inside the token are ignored.

## Error envelope

All errors use the same shape:

```json
{
  "error": {
    "code": "validation_error",
    "message": "The request contains invalid data.",
    "details": { "blood_type": ["Invalid blood type. ..."] }
  }
}
```

| Code | HTTP status | Meaning |
|---|---|---|
| `authentication_failed` | 401 | Token missing, malformed, expired or wrongly signed |
| `permission_denied` | 403 | Authenticated but wrong role / wrong hospital |
| `not_found` | 404 | Record does not exist or is not visible to this user |
| `validation_error` / `bad_request` | 400 | Invalid input or business-rule violation |
| `internal_error` | 500 | Unexpected error — details are never exposed |

## Authentication

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/auth/me/` | Return the resolved profile (`id`, `full_name`, `role`, `hospital_id`) |
| POST | `/api/auth/logout/` | Explain that sign-out happens in the Supabase client |

Login itself uses Supabase Auth directly from the browser (`signInWithPassword`),
so passwords never reach Django.

## Donors

| Method | Endpoint | Access | Purpose |
|---|---|---|---|
| GET | `/api/donors/` | admin, hospital | List with filters, sorting, pagination |
| POST | `/api/donors/` | **admin only** | Create a donor |
| GET | `/api/donors/{id}/` | admin, hospital | Donor detail with eligibility |
| PATCH | `/api/donors/{id}/` | **admin only** | Update a donor |
| DELETE | `/api/donors/{id}/` | **admin only** | Delete a donor |

### Query parameters

| Parameter | Example | Notes |
|---|---|---|
| `blood_type` | `?blood_type=O%2B` | One of the 8 allowed types; invalid → 400 |
| `eligible` | `?eligible=true` | `true`, `false`, `1`, `0` |
| `search` | `?search=carter` | Name for hospitals; name or phone for admins |
| `ordering` | `?ordering=-name` | `name`, `blood_type`, `last_donation`, `created_at`, `eligibility` |
| `page`, `page_size` | `?page=1&page_size=10` | Max `page_size` = 100 |

Response envelope: `{ "count": 12, "next": "...", "previous": null, "results": [...] }`

### Donor representation

```json
{
  "id": "a0000006-0000-4000-8000-000000000006",
  "name": "[TEST] Frank Osei",
  "blood_type": "AB-",
  "phone": null,
  "last_donation": "2026-11-08",
  "eligible": false,
  "has_donation_history": true,
  "days_since_last_donation": 10,
  "days_until_eligible": 80,
  "eligibility_message": "This donor is not eligible yet. Please wait 80 more days.",
  "eligibility_badge": "ineligible",
  "created_at": "...",
  "updated_at": "..."
}
```

`phone` is `null` for hospital users when the donor is ineligible; admins always see it.
`eligibility_badge` is one of `eligible`, `ineligible`, `no_history`. The browser must
display these server values verbatim.

## Blood requests

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/requests/` | Admin sees all; hospital sees only its own |
| POST | `/api/requests/` | Create (hospital is assigned automatically) |
| GET | `/api/requests/{id}/` | Detail (404 if another hospital's request) |
| PATCH | `/api/requests/{id}/` | Update units/status/notes |
| DELETE | `/api/requests/{id}/` | Delete |

Write fields: `blood_type`, `units` (1–10000), `status`, `notes`, optional `hospital_id`
(admin only), optional `donor_id`.

If `donor_id` refers to an ineligible donor, Django returns **400**:

```json
{
  "error": {
    "code": "ineligible_donor",
    "message": "This donor is not eligible to donate yet.",
    "details": {
      "message": "This donor is not eligible to donate yet. Please wait 80 more days.",
      "days_until_eligible": "80",
      "eligibility_badge": "ineligible",
      "donor_id": "a0000006-0000-4000-8000-000000000006"
    }
  }
}
```

## Hospitals

| Method | Endpoint | Access |
|---|---|---|
| GET, POST | `/api/hospitals/` | admin only |
| GET | `/api/hospitals/{id}/` | admin (any) or hospital (own only) |
| PATCH | `/api/hospitals/{id}/` | admin only |

## Analytics

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/analytics/donors-per-blood-type/` | Counts for all 8 types, derived from PostgreSQL |
| GET | `/api/analytics/summary/` | Dashboard counts + recent visible requests |

Example response for the first endpoint:

```json
{
  "A+": 2, "A-": 1, "B+": 2, "B-": 1,
  "AB+": 1, "AB-": 1, "O+": 2, "O-": 2
}
```

## Eligibility rule

`last_donation IS NULL` → eligible (`no_history`, preliminary screening only).
Otherwise `(server_date - last_donation).days >= 90` → eligible. 89 days → ineligible,
90 days → eligible. This is an application screening rule, not a clinical assessment.
