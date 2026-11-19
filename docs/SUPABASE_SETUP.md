# Connect the registry to Supabase (SQL Editor path)

This guide applies the schema and seed data **without sharing database credentials**. It assumes the
recommended architecture: Supabase hosts PostgreSQL and Auth, while the Django API and Next.js
dashboard stay exactly as they are.

If you instead want a full Supabase-native rewrite (PostgREST/RLS/Edge Functions replacing Django),
tell me before running this — that is a different setup.

## Already configured locally

The gitignored env files already contain the **public** project values:

- `backend/.env`: `SUPABASE_URL` and `SUPABASE_JWKS_URL`
- `frontend/.env.local`: Supabase URL and the `sb_publishable_...` key

No `sb_secret_...` key or database password is stored in this repository.

---

## 1. Create real Auth users first

In the Supabase dashboard:

1. Go to **Authentication → Users → Add user**.
2. Create three users, for example:
   - `admin@example.com` — administrator
   - `hospital1@example.com` — hospital A
   - `hospital2@example.com` — hospital B
3. Confirm the emails (or disable email confirmation for this project).
4. Open **Authentication → Users** and copy each user's **UUID**. You need these in step 3.

> Do **not** run `supabase/local/seed_auth_users.sql` in Supabase. That file creates fake users for
> the offline cluster only.

---

## 2. Apply the schema and fictional seed data

In **SQL Editor → New query**, paste and run each file below in this exact order:

1. `supabase/migrations/0001_roles.sql`
2. `supabase/migrations/0002_tables.sql`
3. `supabase/migrations/0003_indexes.sql`
4. `supabase/migrations/0004_functions.sql`
5. `supabase/migrations/0005_rls.sql`
6. `supabase/migrations/0006_request_donor_link.sql`
7. `supabase/migrations/0009_harden_function_search_paths.sql`
8. `supabase/seed.sql`

> The live project also contains corrective migrations `0007_fix_donors_phone_regex` and
> `0008_fix_donors_phone_regex_literal_plus`, which fixed the donor phone CHECK expression after
> the first apply. `0002_tables.sql` now contains the corrected `[+]` expression, so fresh projects
> do not need those two corrective migrations.

You can open each file from your local clone and paste its full contents into the editor.

### Do not run these in Supabase

| File | Why |
|---|---|
| `supabase/local/0000_auth_emulation.sql` | Supabase already provides the `auth` schema and roles |
| `supabase/local/seed_auth_users.sql` | Creates fake local-only users with fake passwords |
| `supabase/tests/verify_database.sql` | Contains psql-only `\echo` commands and local demo UUIDs; use the queries below instead |

The migrations are idempotent (`IF NOT EXISTS`, `DROP POLICY IF EXISTS`, etc.), so re-running them is
safe.

---

## 3. Assign roles to your real users

The `profiles` table deliberately does **not** trust JWT role claims. Run this after replacing the
three placeholders with the UUIDs you copied in step 1:

```sql
SELECT public.assign_role(
    'PASTE_ADMIN_AUTH_UUID'::uuid,
    'admin',
    'Your Admin Name',
    NULL
);

SELECT public.assign_role(
    'PASTE_HOSPITAL1_AUTH_UUID'::uuid,
    'hospital',
    'Hospital One User',
    '11111111-1111-4111-8111-111111111111'
);

SELECT public.assign_role(
    'PASTE_HOSPITAL2_AUTH_UUID'::uuid,
    'hospital',
    'Hospital Two User',
    '22222222-2222-4222-8222-222222222222'
);
```

The two hospital UUIDs are the fictional hospitals inserted by `seed.sql`. The function checks that
each user really exists in `auth.users` and rejects invalid role/hospital combinations. Execution is
revoked from `anon` and `authenticated`, so users cannot promote themselves.

---

## 4. Verify in the SQL Editor

### Row counts

Expected: `3` hospitals, `12` donors, `6` requests, `3` profiles.

```sql
SELECT 'hospitals' AS table_name, count(*) FROM public.hospitals
UNION ALL SELECT 'donors', count(*) FROM public.donors
UNION ALL SELECT 'requests', count(*) FROM public.requests
UNION ALL SELECT 'profiles', count(*) FROM public.profiles
ORDER BY table_name;
```

### RLS enabled on all domain tables

Expected: `true` for all four rows.

```sql
SELECT relname AS table_name, relrowsecurity AS rls_enabled
FROM pg_class
WHERE oid IN (
    'public.donors'::regclass,
    'public.hospitals'::regclass,
    'public.profiles'::regclass,
    'public.requests'::regclass
)
ORDER BY relname;
```

### Required indexes

```sql
SELECT indexname
FROM pg_indexes
WHERE schemaname = 'public' AND indexname LIKE 'ix_%'
ORDER BY indexname;
```

You should see `ix_donors_blood_type`, `ix_donors_last_donation`, `ix_donors_search`,
`ix_requests_hospital_id`, `ix_requests_blood_type`, `ix_requests_hospital_created`,
`ix_profiles_role`, and the other sorting/pagination indexes.

### 90-day eligibility boundary presence

```sql
SELECT
    count(*) FILTER (WHERE last_donation IS NULL) AS no_history,
    count(*) FILTER (WHERE CURRENT_DATE - last_donation >= 90) AS eligible_by_90_days,
    count(*) FILTER (WHERE CURRENT_DATE - last_donation < 90) AS ineligible
FROM public.donors;
```

You should see at least one donor in each category. The server — not the browser — calculates the
final `eligible`, `days_until_eligible` and `eligibility_badge` fields.

---

## 5. Point Django at the hosted database (do this locally)

Running the SQL above creates the tables in Supabase, but the app still uses the isolated local
database until `DATABASE_URL` is changed. Set it in `backend/.env` yourself — no need to paste it
here:

```text
DATABASE_URL=postgresql://postgres.qfqfyadsgmmyfcfoaozq:<DB_PASSWORD>@aws-0-<REGION>.pooler.supabase.com:5432/postgres?sslmode=require
```

- `qfqfyadsgmmyfcfoaozq` is your project ref.
- Replace `<REGION>` and `<DB_PASSWORD>` with the values from **Project Settings → Database →
  Connection string**.
- The session pooler on port `5432` is recommended for Django. Append `?sslmode=require`.
- `backend/.env` is gitignored; never commit it.

Then restart the backend and I can run the full verification suite against Supabase.

---

## 6. Before a real deployment

- Set `DJANGO_DEBUG=false` in `backend/.env` so `POST /api/auth/dev-login/` is disabled.
- Set a strong `DJANGO_SECRET_KEY`, real `DJANGO_ALLOWED_HOSTS` and real `CORS_ALLOWED_ORIGINS`.
- Remove or set `NEXT_PUBLIC_ALLOW_DEV_LOGIN=false` in `frontend/.env.local`.
- Use real Supabase Auth sign-in in the browser; Django verifies each access token through JWKS.

---

## What to tell me after running this

Reply with:

1. **SQL applied** — all seven files ran without errors.
2. **UUIDs assigned** — the three `assign_role` calls succeeded (you do not need to paste the UUIDs).
3. **DATABASE_URL updated locally** — if you want me to switch the running app to Supabase and
   re-run tests/curl checks.

I will then verify the connection and confirm the dashboards work with real Supabase Auth users.
