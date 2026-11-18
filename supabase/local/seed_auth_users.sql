-- LOCAL DEVELOPMENT ONLY. Never run this against a real Supabase project.
-- Creates fake Supabase Auth users so profile foreign keys and JWT-based tests work
-- in the isolated local PostgreSQL cluster.
-- The passwords below are obviously fake, test-only values.

INSERT INTO auth.users (id, instance_id, aud, role, email, encrypted_password, email_confirmed_at, created_at, updated_at)
VALUES
    ('b0000000-0000-4000-8000-000000000001', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'admin.test@example.invalid',   crypt('TEST-ONLY-password-1', gen_salt('bf')), now(), now(), now()),
    ('b0000000-0000-4000-8000-000000000002', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'hospital1.test@example.invalid', crypt('TEST-ONLY-password-2', gen_salt('bf')), now(), now(), now()),
    ('b0000000-0000-4000-8000-000000000003', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'hospital2.test@example.invalid', crypt('TEST-ONLY-password-3', gen_salt('bf')), now(), now(), now())
ON CONFLICT (id) DO NOTHING;

SELECT public.assign_role('b0000000-0000-4000-8000-000000000001', 'admin',    '[TEST] Admin User',       NULL);
SELECT public.assign_role('b0000000-0000-4000-8000-000000000002', 'hospital', '[TEST] Hospital One User', '11111111-1111-4111-8111-111111111111');
SELECT public.assign_role('b0000000-0000-4000-8000-000000000003', 'hospital', '[TEST] Hospital Two User', '22222222-2222-4222-8222-222222222222');
