-- 0007_fix_donors_phone_regex.sql
-- Corrective migration: the deployed donors_phone_format constraint from 0002
-- was transmitted with an over-escaped regex (two backslashes). Restore the
-- intended single-backslash regex from supabase/migrations/0002_tables.sql.
-- No data is modified; only the CHECK constraint is replaced.

ALTER TABLE public.donors DROP CONSTRAINT IF EXISTS donors_phone_format;

ALTER TABLE public.donors
    ADD CONSTRAINT donors_phone_format
    CHECK (phone ~ '^\+?[0-9][0-9() .-]{6,35}$');
