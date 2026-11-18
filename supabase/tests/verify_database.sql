-- verify_database.sql — executable database acceptance tests.
-- Run with:  psql -v ON_ERROR_STOP=1 -f supabase/tests/verify_database.sql
-- Any failed assertion aborts the script with a non-zero exit code.

\echo '== Row counts =='
DO $t$
BEGIN
    IF (SELECT count(*) FROM public.hospitals) < 3 THEN
        RAISE EXCEPTION 'Expected at least 3 hospitals';
    END IF;
    IF (SELECT count(*) FROM public.donors) < 10 THEN
        RAISE EXCEPTION 'Expected at least 10 donors';
    END IF;
    IF (SELECT count(*) FROM public.requests) < 5 THEN
        RAISE EXCEPTION 'Expected at least 5 requests';
    END IF;
    IF (SELECT count(DISTINCT blood_type) FROM public.donors) <> 8 THEN
        RAISE EXCEPTION 'Sample data must cover all 8 blood types';
    END IF;
    IF (SELECT count(*) FROM public.donors WHERE last_donation = CURRENT_DATE - INTERVAL '10 days') < 1 THEN
        RAISE EXCEPTION 'Break-It donor (10 days ago) is missing';
    END IF;
END
$t$;

\echo '== CHECK constraints =='
DO $t$
BEGIN
    BEGIN
        INSERT INTO public.donors (name, blood_type, phone) VALUES ('[TEST] Bad Type', 'XX', '+15550999001');
        RAISE EXCEPTION 'Invalid blood type was accepted';
    EXCEPTION WHEN check_violation THEN NULL;
    END;

    BEGIN
        INSERT INTO public.requests (hospital_id, blood_type, units)
        VALUES ('11111111-1111-4111-8111-111111111111', 'O+', 0);
        RAISE EXCEPTION 'Zero units were accepted';
    EXCEPTION WHEN check_violation THEN NULL;
    END;

    BEGIN
        INSERT INTO public.profiles (id, full_name, role, hospital_id)
        VALUES ('b0000000-0000-4000-8000-000000000001', '[TEST] Escalation', 'superadmin', NULL);
        RAISE EXCEPTION 'Invalid role was accepted';
    EXCEPTION WHEN check_violation THEN NULL;
    END;

    BEGIN
        INSERT INTO public.requests (hospital_id, blood_type, units)
        VALUES ('99999999-9999-4999-8999-999999999999', 'O+', 1);
        RAISE EXCEPTION 'Invalid hospital foreign key was accepted';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;
END
$t$;

\echo '== Indexes =='
DO $t$
DECLARE
    expected text[] := ARRAY[
        'ix_donors_blood_type', 'ix_donors_last_donation', 'ix_requests_hospital_id',
        'ix_requests_blood_type', 'ix_profiles_role', 'ix_donors_search',
        'ix_donors_created_at', 'ix_requests_hospital_created'
    ];
    idx text;
BEGIN
    FOREACH idx IN ARRAY expected LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = idx) THEN
            RAISE EXCEPTION 'Missing index %', idx;
        END IF;
    END LOOP;
END
$t$;

\echo '== RLS enabled =='
DO $t$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_class
        WHERE oid IN ('public.donors'::regclass, 'public.hospitals'::regclass,
                      'public.profiles'::regclass, 'public.requests'::regclass)
          AND relrowsecurity = false
    ) THEN
        RAISE EXCEPTION 'RLS is disabled on at least one domain table';
    END IF;
END
$t$;

\echo '== Eligibility boundary data =='
SELECT blood_type,
       count(*) AS donors,
       count(*) FILTER (WHERE last_donation IS NULL) AS no_history,
       count(*) FILTER (WHERE CURRENT_DATE - last_donation >= 90) AS eligible_by_90_day_rule
FROM public.donors
GROUP BY blood_type
ORDER BY blood_type;

\echo '== RLS behaviour: hospital user =='
SET ROLE authenticated;
SELECT set_config('request.jwt.claim.sub', 'b0000000-0000-4000-8000-000000000002', false);

DO $t$
BEGIN
    IF (SELECT count(*) FROM public.donors) = 0 THEN
        RAISE EXCEPTION 'Hospital user cannot read donors';
    END IF;

    IF EXISTS (SELECT 1 FROM public.requests WHERE hospital_id = '22222222-2222-4222-8222-222222222222') THEN
        RAISE EXCEPTION 'Hospital user can read another hospital''s requests';
    END IF;

    BEGIN
        INSERT INTO public.donors (name, blood_type, phone) VALUES ('[TEST] RLS Should Block', 'O+', '+15550999002');
        RAISE EXCEPTION 'Hospital user was allowed to create a donor';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;

    BEGIN
        UPDATE public.profiles SET role = 'admin' WHERE id = 'b0000000-0000-4000-8000-000000000002';
        RAISE EXCEPTION 'Hospital user was allowed to escalate its role';
    EXCEPTION WHEN insufficient_privilege OR check_violation THEN NULL;
    END;
END
$t$;

\echo '== RLS behaviour: unauthenticated (no JWT claims) =='
SELECT set_config('request.jwt.claim.sub', '', false);
DO $t$
BEGIN
    IF (SELECT count(*) FROM public.donors) <> 0 THEN
        RAISE EXCEPTION 'Anonymous user can read donors';
    END IF;
END
$t$;

RESET ROLE;
SELECT set_config('request.jwt.claim.sub', '', false);

\echo 'ALL DATABASE ASSERTIONS PASSED'
