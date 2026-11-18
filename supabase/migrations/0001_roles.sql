-- 0001_roles.sql
-- Supabase already provides these roles; the DO blocks make the migration also
-- runnable on a plain PostgreSQL cluster used for local development and tests.
-- gen_random_uuid() is built in from PostgreSQL 13, so no extension is required.

DO $migration$
BEGIN
    BEGIN
        CREATE ROLE anon NOLOGIN NOINHERIT;
    EXCEPTION WHEN duplicate_object THEN NULL;
    END;

    BEGIN
        CREATE ROLE authenticated NOLOGIN NOINHERIT;
    EXCEPTION WHEN duplicate_object THEN NULL;
    END;

    BEGIN
        CREATE ROLE service_role NOLOGIN NOINHERIT BYPASSRLS;
    EXCEPTION WHEN duplicate_object THEN NULL;
        -- On Supabase this role already has BYPASSRLS.
    END;
END
$migration$;

GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;

-- Default privileges keep future objects created by postgres usable by the API roles.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO authenticated, service_role;
