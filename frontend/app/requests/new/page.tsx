"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState, type FormEvent } from "react";

import { useAuth } from "@/components/AuthProvider";
import { AppShell } from "@/components/AppShell";
import { EligibilityBadge } from "@/components/EligibilityBadge";
import { LoadingState, SuccessBanner } from "@/components/StateViews";
import { useAsync } from "@/hooks/useAsync";
import { isIneligibleDonorError } from "@/lib/api";
import { BLOOD_TYPES } from "@/lib/constants";
import { errorMessage } from "@/lib/errors";
import { listDonors, getDonor } from "@/services/donors";
import { listHospitals } from "@/services/hospitals";
import { createRequest } from "@/services/requests";
import type { BloodRequest, BloodRequestWritePayload, Donor } from "@/types";

const fieldClass = "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-rose-500";

function NewRequestForm() {
  const searchParams = useSearchParams();
  const { profile } = useAuth();
  const isAdmin = profile?.role === "admin";
  const initialDonor = searchParams.get("donor") ?? "";

  const [bloodType, setBloodType] = useState("O+");
  const [units, setUnits] = useState("1");
  const [notes, setNotes] = useState("");
  const [hospitalId, setHospitalId] = useState("");
  const [selectedDonor, setSelectedDonor] = useState(initialDonor);
  const [donorSearch, setDonorSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [created, setCreated] = useState<BloodRequest | null>(null);

  const hospitalsQuery = useAsync(
    async (signal) => (isAdmin ? await listHospitals(signal) : null),
    [isAdmin],
  );
  const donorsQuery = useAsync(
    (signal) => listDonors({ eligible: true, search: donorSearch, pageSize: 10 }, signal),
    [donorSearch],
  );
  const selectedQuery = useAsync<Donor | null>(
    (signal) => (selectedDonor ? getDonor(selectedDonor, signal) : Promise.resolve(null)),
    [selectedDonor],
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setCreated(null);
    try {
      const payload: BloodRequestWritePayload = {
        blood_type: bloodType,
        units: Number(units),
        notes: notes.trim() || null,
        donor_id: selectedDonor || null,
      };
      if (isAdmin) payload.hospital_id = hospitalId;
      const result = await createRequest(payload);
      setCreated(result);
      setNotes("");
      setSelectedDonor("");
    } catch (reason) {
      setError(reason);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell
      title="New blood request"
      description="Hospital staff are scoped to their own hospital. Donor eligibility is re-checked by the server when you submit."
      actions={
        <Link
          href="/requests"
          className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
        >
          ← All requests
        </Link>
      }
    >
      <div className="mx-auto max-w-3xl space-y-5">
        {created ? (
          <SuccessBanner>
            <p className="font-semibold">Request created successfully.</p>
            <p className="mt-1">
              {created.blood_type} × {created.units} for {created.hospital_name}.{" "}
              <Link href="/requests" className="underline">
                View requests
              </Link>
            </p>
          </SuccessBanner>
        ) : null}

        {error ? (
          <div className="rounded-xl border border-rose-200 bg-rose-50 p-5" role="alert">
            <h2 className="text-sm font-semibold text-rose-900">
              {isIneligibleDonorError(error) ? "The server rejected this donor" : "Request failed"}
            </h2>
            <p className="mt-1 text-sm text-rose-700">{errorMessage(error)}</p>
            {isIneligibleDonorError(error) ? (
              <p className="mt-2 text-xs text-rose-600">
                Eligibility was decided by the API, not by this form. Choose an eligible donor or
                leave the donor unassigned.
              </p>
            ) : null}
          </div>
        ) : null}

        <form onSubmit={handleSubmit} className="space-y-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          {isAdmin ? (
            <div>
              <label htmlFor="hospital" className="block text-sm font-medium text-slate-700">
                Hospital
              </label>
              {hospitalsQuery.loading ? (
                <p className="mt-2 text-sm text-slate-500">Loading hospitals…</p>
              ) : hospitalsQuery.error ? (
                <p className="mt-2 text-sm text-rose-600">{hospitalsQuery.error}</p>
              ) : (
                <select
                  id="hospital"
                  required
                  value={hospitalId}
                  onChange={(event) => setHospitalId(event.target.value)}
                  className={fieldClass}
                >
                  <option value="">Select a hospital…</option>
                  {hospitalsQuery.data?.results.map((hospital) => (
                    <option key={hospital.id} value={hospital.id}>
                      {hospital.name}
                    </option>
                  ))}
                </select>
              )}
            </div>
          ) : (
            <div className="rounded-lg bg-slate-50 p-4 text-sm text-slate-600">
              Hospital: <span className="font-semibold">your registered hospital</span>
              <p className="mt-1 text-xs text-slate-500">
                The API assigns this automatically from your verified profile.
              </p>
            </div>
          )}

          <div className="grid gap-5 sm:grid-cols-2">
            <div>
              <label htmlFor="request-type" className="block text-sm font-medium text-slate-700">
                Blood type
              </label>
              <select
                id="request-type"
                value={bloodType}
                onChange={(event) => setBloodType(event.target.value)}
                className={fieldClass}
              >
                {BLOOD_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="units" className="block text-sm font-medium text-slate-700">
                Units needed
              </label>
              <input
                id="units"
                type="number"
                min={1}
                max={10000}
                required
                value={units}
                onChange={(event) => setUnits(event.target.value)}
                className={fieldClass}
              />
            </div>
          </div>

          <div>
            <label htmlFor="notes" className="block text-sm font-medium text-slate-700">
              Notes <span className="font-normal text-slate-400">(optional)</span>
            </label>
            <textarea
              id="notes"
              rows={3}
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              className={fieldClass}
              placeholder="Urgency, scheduling details, or other context"
            />
          </div>

          <div className="rounded-xl border border-slate-200 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 className="text-sm font-semibold">Donor <span className="font-normal text-slate-400">(optional)</span></h2>
                <p className="text-xs text-slate-500">Only eligible donors are returned by the API.</p>
              </div>
              {selectedDonor ? (
                <button
                  type="button"
                  onClick={() => setSelectedDonor("")}
                  className="text-xs font-semibold text-rose-600 hover:underline"
                >
                  Clear selection
                </button>
              ) : null}
            </div>

            {selectedQuery.loading ? <div className="mt-3"><LoadingState label="Checking donor…" /></div> : null}
            {selectedQuery.data ? (
              <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-lg bg-emerald-50 p-3">
                <div>
                  <p className="text-sm font-semibold text-emerald-900">{selectedQuery.data.name}</p>
                  <p className="text-xs text-emerald-700">
                    {selectedQuery.data.blood_type} · {selectedQuery.data.eligibility_message}
                  </p>
                </div>
                <EligibilityBadge badge={selectedQuery.data.eligibility_badge} compact />
              </div>
            ) : null}

            {!selectedDonor ? (
              <div className="mt-4">
                <label htmlFor="donor-search" className="block text-xs font-semibold text-slate-600">
                  Find an eligible donor
                </label>
                <input
                  id="donor-search"
                  type="search"
                  value={donorSearch}
                  onChange={(event) => setDonorSearch(event.target.value)}
                  placeholder="Search by name"
                  className={fieldClass}
                />
                <div className="mt-3 max-h-56 space-y-2 overflow-y-auto">
                  {donorsQuery.loading ? <p className="text-sm text-slate-500">Loading donors…</p> : null}
                  {donorsQuery.error ? <p className="text-sm text-rose-600">{donorsQuery.error}</p> : null}
                  {donorsQuery.data && !donorsQuery.data.results.length ? (
                    <p className="text-sm text-slate-500">No eligible donors found.</p>
                  ) : null}
                  {donorsQuery.data?.results.map((donor) => (
                    <button
                      key={donor.id}
                      type="button"
                      onClick={() => setSelectedDonor(donor.id)}
                      className="flex w-full items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-left hover:border-rose-300 hover:bg-rose-50/60"
                    >
                      <span>
                        <span className="block text-sm font-medium">{donor.name}</span>
                        <span className="block text-xs text-slate-500">{donor.blood_type}</span>
                      </span>
                      <span className="text-xs font-semibold text-rose-600">Select</span>
                    </button>
                  ))}
                </div>
              </div>
            ) : null}
          </div>

          <button
            type="submit"
            disabled={busy || (isAdmin && !hospitalId)}
            className="w-full rounded-lg bg-rose-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-rose-700 disabled:opacity-50"
          >
            {busy ? "Creating…" : "Create request"}
          </button>
        </form>
      </div>
    </AppShell>
  );
}

export default function NewRequestPage() {
  return (
    <Suspense fallback={<LoadingState label="Preparing request form…" />}>
      <NewRequestForm />
    </Suspense>
  );
}
