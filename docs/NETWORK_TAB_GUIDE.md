# Network tab guide

Use this guide to evidence that the browser and server enforce the rules independently.
Open DevTools (**F12**) → **Network**, tick **Preserve log**, and select **Fetch/XHR**.

## 1. Sign in

1. Open `http://127.0.0.1:3000/login`.
2. Choose an offline demo account (or sign in with Supabase when configured).
3. Watch these entries:
   - `POST /api/auth/dev-login/` (demo only) — `200 OK`.
   - `GET /api/auth/me/` — `200 OK`, returns `id`, `full_name`, `role`, `hospital_id`.

Click `GET /api/auth/me/` → **Headers**. Confirm the request contains:

```http
Authorization: Bearer eyJ...
```

The role shown in the Response comes from `public.profiles`, not from the JWT role claim
and not from a browser-side variable.

## 2. Donor search and eligibility

Navigate to **Donors**. Change blood type to `O+`, eligibility to `Eligible only`, then sort
by name. Inspect:

```http
GET /api/donors/?blood_type=O%2B&eligible=true&ordering=name&page=1&page_size=10
```

Check the Response:

- `count`, `next`, `previous`, `results` envelope (pagination is server-side).
- Each donor has `eligible`, `has_donation_history`, `days_since_last_donation`,
  `days_until_eligible`, `eligibility_message`, `eligibility_badge`.
- `O+` is URL-encoded as `O%2B` — proof the frontend did not build a broken query string.
- For a hospital account, an ineligible donor has `"phone": null`.

## 3. Create a request with an ineligible donor

Open a donor known to be ineligible (seeded `[TEST] Ben Shaw`, 30 days since donation),
click **Create a request with this donor**, then submit. Inspect:

```http
POST /api/requests/
```

Expected:

- Status `400 Bad Request`.
- Response body:
  ```json
  {
    "error": {
      "code": "ineligible_donor",
      "message": "This donor is not eligible to donate yet.",
      "details": {
        "message": "This donor is not eligible to donate yet. Please wait 60 more days.",
        "days_until_eligible": 60,
        "eligibility_badge": "ineligible",
        "donor_id": "a0000002-0000-4000-8000-000000000002"
      }
    }
  }
  ```

The exact `days_until_eligible` depends on the current date. The important evidence is the
`400` status and the `ineligible_donor` code produced by Django.

## 4. Hospital scoping

Sign in as **Hospital A**, then open **Requests**. Inspect:

```http
GET /api/requests/?page=1&page_size=10
```

Every `hospital_name` in the response should be Hospital A. Sign in as **Administrator**
and repeat: all hospitals appear. This is enforced in the API queryset, not by hiding rows
in the table.

## 5. What to capture for a bug report

- Request **Name**, **Status**, **Method**, and **URL**.
- **Request Headers** (redact the `Bearer` token; keep the header name).
- **Request Payload** (redact personal data if required).
- **Response** body and status.
- **Timing** tab if the complaint is about slowness.
- Console errors from the **Console** tab.

Never paste a full access token, service-role key, or database password into a report.
