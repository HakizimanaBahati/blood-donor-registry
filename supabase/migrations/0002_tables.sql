-- 0002_tables.sql
-- Source of truth for the four domain tables. Django models for these tables are
-- declared managed = False so makemigrations never redefines them.

-- ── Hospitals ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.hospitals (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name        varchar(200) NOT NULL,
    location    varchar(200),
    phone       varchar(40),
    created_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT hospitals_name_not_blank CHECK (length(btrim(name)) > 1)
);

COMMENT ON TABLE public.hospitals IS 'Hospital organisations that can submit blood requests.';

-- ── Donors ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.donors (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name           varchar(200) NOT NULL,
    blood_type     varchar(3) NOT NULL,
    last_donation  date,
    phone          varchar(40) NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT donors_name_not_blank CHECK (length(btrim(name)) > 1),
    CONSTRAINT donors_blood_type_valid CHECK (
        blood_type IN ('A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-')
    ),
    CONSTRAINT donors_phone_format CHECK (phone ~ '^\+?[0-9][0-9() .-]{6,35}$')
);

COMMENT ON COLUMN public.donors.last_donation IS
    'NULL means the donor has no donation history; the registry treats this as eligible for preliminary screening.';

-- ── Profiles (one row per Supabase Auth user) ────────────────────────────────
CREATE TABLE IF NOT EXISTS public.profiles (
    id           uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name    varchar(200) NOT NULL,
    role         varchar(20) NOT NULL,
    hospital_id  uuid REFERENCES public.hospitals(id) ON DELETE SET NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT profiles_role_valid CHECK (role IN ('admin', 'hospital')),
    CONSTRAINT profiles_role_hospital_consistent CHECK (
        (role = 'admin'    AND hospital_id IS NULL) OR
        (role = 'hospital' AND hospital_id IS NOT NULL)
    ),
    CONSTRAINT profiles_full_name_not_blank CHECK (length(btrim(full_name)) > 1)
);

COMMENT ON TABLE public.profiles IS
    'Application role store. role is deliberately NOT taken from the Supabase JWT.';

-- ── Blood requests ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.requests (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    hospital_id         uuid NOT NULL REFERENCES public.hospitals(id) ON DELETE CASCADE,
    blood_type          varchar(3) NOT NULL,
    units               integer NOT NULL,
    status              varchar(20) NOT NULL DEFAULT 'pending',
    notes               text,
    requester_profile_id uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT requests_blood_type_valid CHECK (
        blood_type IN ('A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-')
    ),
    CONSTRAINT requests_units_positive CHECK (units > 0 AND units <= 10000),
    CONSTRAINT requests_status_valid CHECK (status IN ('pending', 'fulfilled', 'cancelled')),
    CONSTRAINT requests_notes_length CHECK (notes IS NULL OR length(notes) <= 1000)
);

COMMENT ON TABLE public.requests IS
    'Blood requests created by hospital accounts. Row-level security limits each hospital to its own rows.';
