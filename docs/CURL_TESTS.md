# Three copy-paste API checks (PowerShell + `curl.exe`)

These three requests prove the most important runtime behaviour: authentication,
server-side search with pagination, and rejection of an ineligible donor. They use the
**development-only** login endpoint, so the Django server must be running with
`DJANGO_DEBUG=true`. No real credentials are used.

> PowerShell aliases `curl` to `Invoke-WebRequest`. Always call `curl.exe`.
> Write JSON bodies to a file first; inline JSON is mangled by PowerShell quoting.

## 1. Obtain a development token

Create `C:\Users\user\AppData\Local\Temp\opencode\dev-login.json`:

```json
{"user":"hospital1"}
```

Then run:

```bash
curl.exe -i -X POST http://127.0.0.1:8000/api/auth/dev-login/ -H "Content-Type: application/json" -d "@C:\Users\user\AppData\Local\Temp\opencode\dev-login.json"
```

Expected: `200 OK` with `access_token`, `role: "hospital"` and `user_id`. Copy the
`access_token` value into `<TOKEN>` in the next two requests.

## 2. Search donors with server-side filters and pagination

```bash
curl.exe -i "http://127.0.0.1:8000/api/donors/?blood_type=O%2B&page=1&page_size=2" -H "Authorization: Bearer <TOKEN>"
```

Expected: `200 OK` with a paginated envelope (`count`, `next`, `previous`, `results`).
Every result includes server-generated `eligible`, `days_until_eligible` and
`eligibility_badge` fields. Omit the header to see `401 Unauthorized`.

## 3. Prove the server rejects an ineligible donor

Create `C:\Users\user\AppData\Local\Temp\opencode\ineligible-request.json`:

```json
{"blood_type":"O+","units":1,"donor_id":"a0000002-0000-4000-8000-000000000002","notes":"[TEST] must be rejected"}
```

Then run:

```bash
curl.exe -i -X POST http://127.0.0.1:8000/api/requests/ -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" -d "@C:\Users\user\AppData\Local\Temp\opencode\ineligible-request.json"
```

Expected: `400 Bad Request` with `error.code = "ineligible_donor"` and
`error.details.days_until_eligible`. The frontend never decides eligibility; Django does.

---

For the full endpoint list, see [API_DOCUMENTATION.md](API_DOCUMENTATION.md).
