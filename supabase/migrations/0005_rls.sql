-- 0005_rls.sql
-- Row Level Security. These policies govern direct Supabase client (PostgREST)
-- access. The Django API additionally enforces the same rules in application
-- code using DRF permissions, so security does not rely on one layer alone.

-- ── Grants: anon gets nothing ────────────────────────────────────────────────
REVOKE ALL ON public.donors, public.hospitals, public.profiles, public.requests FROM anon, PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.donors, public.hospitals, public.requests TO authenticated;

-- Profiles: users may read their own row and change only their display name.
-- Column-level UPDATE grant prevents role/hospital_id escalation through PostgREST.
REVOKE ALL ON public.profiles FROM authenticated;
GRANT SELECT ON public.profiles TO authenticated;
GRANT UPDATE (full_name) ON public.profiles TO authenticated;

-- ── donors ───────────────────────────────────────────────────────────────────
ALTER TABLE public.donors ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS donors_select_policy ON public.donors;
CREATE POLICY donors_select_policy ON public.donors
    FOR SELECT TO authenticated
    USING (public.bdr_is_admin() OR public.bdr_is_hospital());

DROP POLICY IF EXISTS donors_insert_policy ON public.donors;
CREATE POLICY donors_insert_policy ON public.donors
    FOR INSERT TO authenticated
    WITH CHECK (public.bdr_is_admin());

DROP POLICY IF EXISTS donors_update_policy ON public.donors;
CREATE POLICY donors_update_policy ON public.donors
    FOR UPDATE TO authenticated
    USING (public.bdr_is_admin())
    WITH CHECK (public.bdr_is_admin());

DROP POLICY IF EXISTS donors_delete_policy ON public.donors;
CREATE POLICY donors_delete_policy ON public.donors
    FOR DELETE TO authenticated
    USING (public.bdr_is_admin());

-- ── hospitals ────────────────────────────────────────────────────────────────
ALTER TABLE public.hospitals ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS hospitals_select_policy ON public.hospitals;
CREATE POLICY hospitals_select_policy ON public.hospitals
    FOR SELECT TO authenticated
    USING (public.bdr_is_admin() OR id = public.bdr_hospital_id());

DROP POLICY IF EXISTS hospitals_insert_policy ON public.hospitals;
CREATE POLICY hospitals_insert_policy ON public.hospitals
    FOR INSERT TO authenticated
    WITH CHECK (public.bdr_is_admin());

DROP POLICY IF EXISTS hospitals_update_policy ON public.hospitals;
CREATE POLICY hospitals_update_policy ON public.hospitals
    FOR UPDATE TO authenticated
    USING (public.bdr_is_admin())
    WITH CHECK (public.bdr_is_admin());

DROP POLICY IF EXISTS hospitals_delete_policy ON public.hospitals;
CREATE POLICY hospitals_delete_policy ON public.hospitals
    FOR DELETE TO authenticated
    USING (public.bdr_is_admin());

-- ── profiles ─────────────────────────────────────────────────────────────────
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS profiles_select_policy ON public.profiles;
CREATE POLICY profiles_select_policy ON public.profiles
    FOR SELECT TO authenticated
    USING (id = public.bdr_uid() OR public.bdr_is_admin());

DROP POLICY IF EXISTS profiles_update_policy ON public.profiles;
CREATE POLICY profiles_update_policy ON public.profiles
    FOR UPDATE TO authenticated
    USING (id = public.bdr_uid())
    WITH CHECK (id = public.bdr_uid());

-- No INSERT/DELETE policy: profiles are created only by the SECURITY DEFINER
-- assign_role() function or by a trusted backend/service-role process.

-- ── requests ─────────────────────────────────────────────────────────────────
ALTER TABLE public.requests ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS requests_select_policy ON public.requests;
CREATE POLICY requests_select_policy ON public.requests
    FOR SELECT TO authenticated
    USING (public.bdr_is_admin() OR hospital_id = public.bdr_hospital_id());

DROP POLICY IF EXISTS requests_insert_policy ON public.requests;
CREATE POLICY requests_insert_policy ON public.requests
    FOR INSERT TO authenticated
    WITH CHECK (public.bdr_is_admin() OR hospital_id = public.bdr_hospital_id());

DROP POLICY IF EXISTS requests_update_policy ON public.requests;
CREATE POLICY requests_update_policy ON public.requests
    FOR UPDATE TO authenticated
    USING (public.bdr_is_admin() OR hospital_id = public.bdr_hospital_id())
    WITH CHECK (public.bdr_is_admin() OR hospital_id = public.bdr_hospital_id());

DROP POLICY IF EXISTS requests_delete_policy ON public.requests;
CREATE POLICY requests_delete_policy ON public.requests
    FOR DELETE TO authenticated
    USING (public.bdr_is_admin() OR hospital_id = public.bdr_hospital_id());
