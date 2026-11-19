-- 0008_fix_donors_phone_regex_literal_plus.sql
-- Second corrective migration. The previous corrective migration was also
-- over-escaped during transmission. This version uses the POSIX character
-- class [+] instead of \+, so no backslash escaping is required.
-- Semantics are identical: optional leading '+', then 7-36 allowed characters.
-- No data is modified; only the CHECK constraint is replaced.

ALTER TABLE public.donors DROP CONSTRAINT IF EXISTS donors_phone_format;

ALTER TABLE public.donors
    ADD CONSTRAINT donors_phone_format
    CHECK (phone ~ '^[+]?[0-9][0-9() .-]{6,35}$');
