"use client";

import { useState, type FormEvent } from "react";

import { useAuth } from "@/components/AuthProvider";
import { AppShell } from "@/components/AppShell";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { EmptyState, ErrorState, LoadingState, SuccessBanner } from "@/components/StateViews";
import { useAsync } from "@/hooks/useAsync";
import { errorMessage } from "@/lib/errors";
import { formatDate } from "@/lib/format";
import { createHospital, getHospital, listHospitals } from "@/services/hospitals";
import type { Hospital } from "@/types";

const fieldClass = "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-rose-500";

function HospitalsContent() {
  const { profile } = useAuth();
  const isAdmin = profile?.role === "admin";

  const hospitalsQuery = useAsync<Hospital[] | null>(
    async (signal) => {
      if (isAdmin) {
        const page = await listHospitals(signal);
        return page.results;
      }
      if (!profile?.hospital_id) return [];
      return [await getHospital(profile.hospital_id, signal)];
    },
    [isAdmin, profile?.hospital_id],
  );

  const [name, setName] = useState("");
  const [location, setLocation] = useState("");
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const hospital = await createHospital({
        name,
        location: location.trim() || null,
        phone: phone.trim() || null,
      });
      setNotice(`${hospital.name} was added.`);
      setName("");
      setLocation("");
      setPhone("");
      hospitalsQuery.reload();
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell
      title="Hospitals"
      description={
        isAdmin
          ? "Manage participating hospitals and their contact details."
          : "Your hospital’s registered details."
      }
    >
      {hospitalsQuery.loading ? <LoadingState label="Loading hospitals…" /> : null}
      {hospitalsQuery.error ? (
        <ErrorState message={hospitalsQuery.error} onRetry={hospitalsQuery.reload} />
      ) : null}

      {notice ? <SuccessBanner>{notice}</SuccessBanner> : null}
      {error ? <ErrorState title="Could not add hospital" message={error} /> : null}

      {!hospitalsQuery.loading && !hospitalsQuery.error && hospitalsQuery.data ? (
        <div className="grid gap-6 lg:grid-cols-3">
          <section className="space-y-4 lg:col-span-2">
            {hospitalsQuery.data.length ? (
              hospitalsQuery.data.map((hospital) => (
                <article
                  key={hospital.id}
                  className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h2 className="text-lg font-semibold">{hospital.name}</h2>
                      <p className="text-sm text-slate-500">{hospital.location ?? "No location recorded"}</p>
                    </div>
                    <span className="text-xs text-slate-400">Registered {formatDate(hospital.created_at)}</span>
                  </div>
                  <p className="mt-3 text-sm text-slate-600">
                    Phone: {hospital.phone ?? <span className="italic text-slate-400">Not recorded</span>}
                  </p>
                </article>
              ))
            ) : (
              <EmptyState title="No hospitals found" description="Add a hospital to start assigning requests." />
            )}
          </section>

          {isAdmin ? (
            <aside className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-base font-semibold">Add hospital</h2>
              <form onSubmit={handleCreate} className="mt-4 space-y-4">
                <div>
                  <label htmlFor="hospital-name" className="block text-sm font-medium">
                    Name
                  </label>
                  <input
                    id="hospital-name"
                    required
                    minLength={2}
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                    className={fieldClass}
                  />
                </div>
                <div>
                  <label htmlFor="hospital-location" className="block text-sm font-medium">
                    Location <span className="font-normal text-slate-400">(optional)</span>
                  </label>
                  <input
                    id="hospital-location"
                    value={location}
                    onChange={(event) => setLocation(event.target.value)}
                    className={fieldClass}
                  />
                </div>
                <div>
                  <label htmlFor="hospital-phone" className="block text-sm font-medium">
                    Phone <span className="font-normal text-slate-400">(optional)</span>
                  </label>
                  <input
                    id="hospital-phone"
                    type="tel"
                    value={phone}
                    onChange={(event) => setPhone(event.target.value)}
                    className={fieldClass}
                  />
                </div>
                <button
                  type="submit"
                  disabled={busy}
                  className="w-full rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                >
                  {busy ? "Saving…" : "Add hospital"}
                </button>
              </form>
            </aside>
          ) : null}
        </div>
      ) : null}
    </AppShell>
  );
}

export default function HospitalsPage() {
  return (
    <ProtectedRoute>
      <HospitalsContent />
    </ProtectedRoute>
  );
}
