-- 0009_harden_function_search_paths.sql
-- Supabase's security advisor flags SECURITY DEFINER / trigger functions whose
-- search_path is not pinned. These are the two helpers from 0004_functions.sql
-- that did not already set it. Re-declaring them is safe and idempotent.

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
