# Supabase database setup

## Files

| File | Purpose |
|---|---|
| `migrations/0001_roles.sql` | Supabase-compatible roles and grants (idempotent on plain Postgres) |
| `migrations/0002_tables.sql` | `hospitals`, `donors`, `profiles`, `requests` with PK/FK/CHECK constraints |
| `migrations/0003_indexes.sql` | Required indexes, composite search index, sorting/pagination indexes |
| `migrations/0004_functions.sql` | `updated_at` triggers, JWT claim helpers, secure `assign_role()` bootstrap |
| `migrations/0005_rls.sql` | RLS enablement and role-based policies |
| `seed.sql` | 12 fictional donors (all 8 blood types), 3 hospitals, 6 requests |
| `tests/verify_database.sql` | Executable acceptance assertions |
| `local/` | Plain-Postgres auth emulation and test users — **never use on a real Supabase project** |

All sample records are labelled `[TEST]` and use `@example.invalid` emails and fictional
`+1-555-...` numbers. Donation dates are relative to `CURRENT_DATE`, so the 10-day
Break-It donor never ages out of the exercise.

## Apply to a real Supabase project

1. Create a Supabase project. Note the **Project URL**, **anon key**, and either the
   legacy **JWT secret** or the project's asymmetric signing configuration. Never use
   the service-role key in the browser.
2. Open **SQL Editor → New query** and run each migration in filename order
   (`0001` → `0005`). They are idempotent and safe to re-run.
3. Run `seed.sql` in the SQL Editor.
4. Create the login users in **Authentication → Users → Add user** (email + password).
   Copy each generated user UUID from the dashboard.
5. Assign application roles with the SECURITY DEFINER function (run as the SQL Editor's
   `postgres` role):

```sql
-- Initial admin (hospital_id must be NULL)
SELECT public.assign_role('PASTE_ADMIN_AUTH_USER_UUID', 'admin', 'Admin Name', NULL);

-- Hospital staff (must be linked to a hospital record)
SELECT public.assign_role('PASTE_HOSPITAL_AUTH_USER_UUID', 'hospital', 'Hospital User',
                          '11111111-1111-4111-8111-111111111111');
```

`assign_role()` is revoked from `anon` and `authenticated`, so an ordinary user cannot
promote themselves. `profiles.role` is also protected by a CHECK constraint and a
column-level UPDATE grant, so even direct PostgREST updates cannot change it.

## RLS summary

| Table | SELECT | INSERT / UPDATE / DELETE |
|---|---|---|
| `donors` | admin or hospital | admin only |
| `hospitals` | admin, or the user's own hospital | admin only |
| `profiles` | own row or admin | `full_name` only, own row; role changes only via `assign_role()` |
| `requests` | admin, or rows of the user's hospital | admin, or rows of the user's hospital |

`anon` has no grants on these tables. The Django API enforces the same rules in code,
so a misconfigured database role cannot by itself bypass authorisation.

## Local verification (no Supabase credentials needed)

```powershell
.\scripts\local-db.ps1 start                  # isolated cluster on port 55432
.\scripts\apply-local-migrations.ps1          # migrations + seed + assertions
.\scripts\local-db.ps1 stop
```

On Windows, `local-db.ps1` registers a dedicated `BDRLocalPG` service running as
`NetworkService`. This is required because PostgreSQL refuses to run under an elevated
token, and the service keeps the server alive after the invoking shell exits. No existing
PostgreSQL installation or service is modified.

`apply-local-migrations.ps1` first creates a minimal `auth.users` stand-in
(`supabase/local/0000_auth_emulation.sql`) so the real migrations and seed can run on a
plain PostgreSQL cluster. It ends by running `tests/verify_database.sql`, which asserts
row counts, constraints, indexes, RLS enablement, cross-hospital isolation and anonymous
denial.

## Connection string for Django

Use the Supabase **direct** or **pooler** connection string in `backend/.env`:

```
DATABASE_URL=postgresql://postgres:<password>@<host>:5432/postgres
```

The Django role must be able to read/write the four domain tables and read
`auth.users` is **not** required — Django reads `public.profiles` for role lookup, not
the auth table itself.
