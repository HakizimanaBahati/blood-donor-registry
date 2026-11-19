-- 0004_functions.sql
-- Helper functions, updated_at triggers and the secure role-assignment procedure.

CREATE SCHEMA IF NOT EXISTS auth;

-- Returns the verified Supabase user id from either GUC naming convention used by
-- Supabase/PostgREST. Returns NULL when no JWT claims are present.
CREATE OR REPLACE FUNCTION public.bdr_uid()
RETURNS uuid
LANGUAGE sql
STABLE
SET search_path = public, pg_temp
AS $fn$
    SELECT coalesce(
        nullif(current_setting('request.jwt.claim.sub', true), '')::uuid,
        (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub')::uuid
    );
$fn$;

CREATE OR REPLACE FUNCTION public.bdr_is_admin()
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $fn$
    SELECT EXISTS (
        SELECT 1 FROM public.profiles p
        WHERE p.id = public.bdr_uid() AND p.role = 'admin'
    );
$fn$;

CREATE OR REPLACE FUNCTION public.bdr_is_hospital()
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $fn$
    SELECT EXISTS (
        SELECT 1 FROM public.profiles p
        WHERE p.id = public.bdr_uid() AND p.role = 'hospital'
    );
$fn$;

-- Hospital id associated with the current Supabase user (NULL for admins).
CREATE OR REPLACE FUNCTION public.bdr_hospital_id()
RETURNS uuid
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $fn$
    SELECT p.hospital_id FROM public.profiles p
    WHERE p.id = public.bdr_uid() AND p.role = 'hospital';
$fn$;

-- Policy helper functions are executed as `authenticated` by the RLS policies.
-- Remove the default PUBLIC/anon EXECUTE grant, but keep the grant RLS requires.
REVOKE ALL ON FUNCTION public.bdr_is_admin() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.bdr_is_admin() TO authenticated, service_role;
REVOKE ALL ON FUNCTION public.bdr_is_hospital() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.bdr_is_hospital() TO authenticated, service_role;
REVOKE ALL ON FUNCTION public.bdr_hospital_id() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.bdr_hospital_id() TO authenticated, service_role;

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $fn$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$fn$;

DROP TRIGGER IF EXISTS trg_donors_updated_at ON public.donors;
CREATE TRIGGER trg_donors_updated_at
    BEFORE UPDATE ON public.donors
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

DROP TRIGGER IF EXISTS trg_requests_updated_at ON public.requests;
CREATE TRIGGER trg_requests_updated_at
    BEFORE UPDATE ON public.requests
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ── Secure admin bootstrap ───────────────────────────────────────────────────
-- Run in the Supabase SQL editor AFTER creating the user in Supabase Auth:
--   SELECT public.assign_role('<auth-user-uuid>', 'admin', 'Full Name', NULL);
--   SELECT public.assign_role('<auth-user-uuid>', 'hospital', 'Full Name', '<hospital-uuid>');
-- Execution is revoked from anon/authenticated so users cannot promote themselves.
CREATE OR REPLACE FUNCTION public.assign_role(
    p_user_id     uuid,
    p_role        varchar,
    p_full_name   varchar,
    p_hospital_id uuid DEFAULT NULL
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $fn$
BEGIN
    IF p_role IS NULL OR p_role NOT IN ('admin', 'hospital') THEN
        RAISE EXCEPTION 'Invalid role: %', p_role;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM auth.users WHERE id = p_user_id) THEN
        RAISE EXCEPTION 'No Supabase Auth user with id %', p_user_id;
    END IF;

    IF p_role = 'admin' AND p_hospital_id IS NOT NULL THEN
        RAISE EXCEPTION 'Admin profiles must not be linked to a hospital';
    END IF;

    IF p_role = 'hospital' AND p_hospital_id IS NULL THEN
        RAISE EXCEPTION 'Hospital profiles require a hospital_id';
    END IF;

    INSERT INTO public.profiles (id, full_name, role, hospital_id)
    VALUES (p_user_id, btrim(p_full_name), p_role, p_hospital_id)
    ON CONFLICT (id) DO UPDATE
        SET full_name   = EXCLUDED.full_name,
            role        = EXCLUDED.role,
            hospital_id = EXCLUDED.hospital_id;
END;
$fn$;

REVOKE ALL ON FUNCTION public.assign_role(uuid, varchar, varchar, uuid) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.assign_role(uuid, varchar, varchar, uuid) TO service_role;
