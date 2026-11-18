-- 0003_indexes.sql
-- Indexes for the required filters, composites, sorting and pagination.

-- Required single-column indexes
CREATE INDEX IF NOT EXISTS ix_donors_blood_type    ON public.donors (blood_type);
CREATE INDEX IF NOT EXISTS ix_donors_last_donation ON public.donors (last_donation);
CREATE INDEX IF NOT EXISTS ix_requests_hospital_id ON public.requests (hospital_id);
CREATE INDEX IF NOT EXISTS ix_requests_blood_type  ON public.requests (blood_type);
CREATE INDEX IF NOT EXISTS ix_profiles_role        ON public.profiles (role);

-- Composite index for the main hospital search: blood type + eligibility date + name
CREATE INDEX IF NOT EXISTS ix_donors_search
    ON public.donors (blood_type, last_donation DESC NULLS LAST, name);

-- Sorting / pagination helpers
CREATE INDEX IF NOT EXISTS ix_donors_created_at ON public.donors (created_at DESC);
CREATE INDEX IF NOT EXISTS ix_donors_name       ON public.donors (name);
CREATE INDEX IF NOT EXISTS ix_requests_created_at ON public.requests (created_at DESC);
CREATE INDEX IF NOT EXISTS ix_requests_hospital_created
    ON public.requests (hospital_id, created_at DESC);

-- Avoid duplicate donor contact records even when phone formatting differs
CREATE UNIQUE INDEX IF NOT EXISTS uq_donors_phone_normalized
    ON public.donors (regexp_replace(phone, '[^0-9]', '', 'g'));
