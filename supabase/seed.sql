-- seed.sql — FICTIONAL TEST DATA ONLY.
-- Every record is prefixed/labelled [TEST]. Relative dates keep the 10-day
-- "Break-It Challenge" donor ineligible no matter when the seed is applied.
-- This file does not insert into auth.users; see supabase/README.md for the
-- documented admin bootstrap and local/seed_auth_users.sql for the local cluster.

BEGIN;

INSERT INTO public.hospitals (id, name, location, phone) VALUES
    ('11111111-1111-4111-8111-111111111111', '[TEST] City General Hospital', 'Springfield, IL', '+15550101001'),
    ('22222222-2222-4222-8222-222222222222', '[TEST] Riverside Medical Center', 'Springfield, IL', '+15550101002'),
    ('33333333-3333-4333-8333-333333333333', '[TEST] Northside Community Clinic', 'Shelbyville, IL', '+15550101003')
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.donors (id, name, blood_type, last_donation, phone) VALUES
    ('a0000001-0000-4000-8000-000000000001', '[TEST] Alice Carter',   'A+',  CURRENT_DATE - INTERVAL '120 days', '+15550102001'),
    ('a0000002-0000-4000-8000-000000000002', '[TEST] Ben Shaw',        'A-',  CURRENT_DATE - INTERVAL '30 days',  '+15550102002'),
    ('a0000003-0000-4000-8000-000000000003', '[TEST] Carla Mendes',    'B+',  CURRENT_DATE - INTERVAL '90 days',  '+15550102003'),
    ('a0000004-0000-4000-8000-000000000004', '[TEST] Daniel Kim',      'B-',  CURRENT_DATE - INTERVAL '89 days',  '+15550102004'),
    ('a0000005-0000-4000-8000-000000000005', '[TEST] Emma Rossi',      'AB+', NULL,                               '+15550102005'),
    ('a0000006-0000-4000-8000-000000000006', '[TEST] Frank Osei',      'AB-', CURRENT_DATE - INTERVAL '10 days',  '+15550102006'),
    ('a0000007-0000-4000-8000-000000000007', '[TEST] Grace Patel',     'O+',  CURRENT_DATE - INTERVAL '200 days', '+15550102007'),
    ('a0000008-0000-4000-8000-000000000008', '[TEST] Henry Brooks',    'O-',  CURRENT_DATE - INTERVAL '10 days',  '+15550102008'),
    ('a0000009-0000-4000-8000-000000000009', '[TEST] Isobel Nolan',    'O+',  NULL,                               '+15550102009'),
    ('a0000010-0000-4000-8000-000000000010', '[TEST] James Whitfield', 'A+',  CURRENT_DATE - INTERVAL '45 days',  '+15550102010'),
    ('a0000011-0000-4000-8000-000000000011', '[TEST] Kara Singh',      'O-',  CURRENT_DATE - INTERVAL '365 days', '+15550102011'),
    ('a0000012-0000-4000-8000-000000000012', '[TEST] Liam Turner',     'B+',  NULL,                               '+15550102012')
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.requests (id, hospital_id, blood_type, units, status, notes) VALUES
    ('c0000001-0000-4000-8000-000000000001', '11111111-1111-4111-8111-111111111111', 'O+',  4, 'pending',   '[TEST] Routine stock replenishment'),
    ('c0000002-0000-4000-8000-000000000002', '11111111-1111-4111-8111-111111111111', 'A-',  2, 'fulfilled', '[TEST] Elective procedure'),
    ('c0000003-0000-4000-8000-000000000003', '22222222-2222-4222-8222-222222222222', 'B+',  3, 'pending',   '[TEST] Emergency reserve'),
    ('c0000004-0000-4000-8000-000000000004', '22222222-2222-4222-8222-222222222222', 'AB+', 1, 'cancelled', '[TEST] Cancelled by clinician'),
    ('c0000005-0000-4000-8000-000000000005', '33333333-3333-4333-8333-333333333333', 'O-',  6, 'pending',   '[TEST] Trauma centre request'),
    ('c0000006-0000-4000-8000-000000000006', '11111111-1111-4111-8111-111111111111', 'B-',  2, 'pending',   '[TEST] Weekend coverage')
ON CONFLICT (id) DO NOTHING;

COMMIT;
