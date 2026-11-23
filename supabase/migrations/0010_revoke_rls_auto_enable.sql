-- 0010_revoke_rls_auto_enable.sql
-- Supabase creates rls_auto_enable() as SECURITY DEFINER and grants it to PUBLIC,
-- anon and authenticated. It is a dashboard helper, not part of this registry's
-- API, so clients must not be able to reach it through /rest/v1/rpc/.
-- The guard keeps this migration idempotent on plain PostgreSQL test clusters
-- where the Supabase helper does not exist.

DO $migration$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_proc
        WHERE pronamespace = 'public'::regnamespace
          AND proname = 'rls_auto_enable'
          AND pronargs = 0
    ) THEN
        REVOKE ALL ON FUNCTION public.rls_auto_enable() FROM PUBLIC, anon, authenticated;
    END IF;
END
$migration$;
