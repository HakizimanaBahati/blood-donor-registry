-- 0006_request_donor_link.sql
-- Optional auditable link between a blood request and the donor selected for it.
-- The eligibility check is still performed by Django before this value is stored.
ALTER TABLE public.requests
    ADD COLUMN IF NOT EXISTS donor_id uuid REFERENCES public.donors(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ix_requests_donor_id ON public.requests (donor_id);
