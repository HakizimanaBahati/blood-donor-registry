"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { useAuth } from "@/components/AuthProvider";
import { AppShell } from "@/components/AppShell";
import { EligibilityBadge } from "@/components/EligibilityBadge";
import { ErrorState, LoadingState, SuccessBanner } from "@/components/StateViews";
import { useAsync } from "@/hooks/useAsync";
import { BLOOD_TYPES } from "@/lib/constants";
import { errorMessage } from "@/lib/errors";
import { formatDate, pluralize, todayInputValue } from "@/lib/format";
import { deleteDonor, getDonor, updateDonor } from "@/services/donors";
import type { DonorWritePayload } from "@/types";

const fieldClass = "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-rose-500";

export default function DonorDetailPage() {
  const params = useParams<{ id: string }>();
  const donorId = params.id;
  const router = useRouter();
  const { profile } = useAuth();
  const isAdmin = profile?.role === "admin";

  const donorQuery = useAsync((signal) => getDonor(donorId, signal), [donorId]);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [form, setForm] = useState<DonorWritePayload>({
    name: "",
    blood_type: "A+",
    phone: "",
    last_donation: null,
  });

  useEffect(() => {
    const donor = donorQuery.data;
    if (!donor) return;
    setForm({
      name: donor.name,
      blood_type: donor.blood_type,
      phone: donor.phone ?? "",
      last_donation: donor.last_donation,
    });
  }, [donorQuery.data]);

  async function handleUpdate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setFormError(null);
    setNotice(null);
    try {
      await updateDonor(donorId, form);
      setNotice("Donor details were updated.");
      setEditing(false);
      donorQuery.reload();
    } catch (reason) {
      setFormError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete() {
    if (!window.confirm("Delete this donor permanently?")) return;
    setBusy(true);
    setFormError(null);
    try {
      await deleteDonor(donorId);
      router.push("/donors");
    } catch (reason) {
      setFormError(errorMessage(reason));
      setBusy(false);
    }
  }

  const donor = donorQuery.data;

  return (
    <AppShell
      title="Donor details"
      description="Eligibility below is computed and returned by the API."
      actions={
        <Link
          href="/donors"
          className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
        >
          ← Back to donors
        </Link>
      }
    >
      {donorQuery.loading ? <LoadingState label="Loading donor…" /> : null}
      {donorQuery.error ? <ErrorState message={donorQuery.error} onRetry={donorQuery.reload} /> : null}

      {notice ? <SuccessBanner>{notice}</SuccessBanner> : null}
      {formError ? <ErrorState title="Update failed" message={formError} /> : null}

      {donor ? (
        <div className="grid gap-6 lg:grid-cols-3">
          <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm lg:col-span-2">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-xl font-bold">{donor.name}</h2>
                <p className="mt-1 text-sm text-slate-500">
                  Registered {formatDate(donor.created_at, true)}
                </p>
              </div>
              <span className="rounded-lg bg-rose-50 px-3 py-1.5 text-sm font-bold text-rose-700">
                {donor.blood_type}
              </span>
            </div>

            <dl className="mt-6 grid gap-4 sm:grid-cols-2">
              <div className="rounded-lg bg-slate-50 p-4">
                <dt className="text-xs font-semibold uppercase text-slate-500">Phone</dt>
                <dd className="mt-1 text-sm text-slate-800">
                  {donor.phone ?? "Not available for ineligible donors"}
                </dd>
              </div>
              <div className="rounded-lg bg-slate-50 p-4">
                <dt className="text-xs font-semibold uppercase text-slate-500">Last donation</dt>
                <dd className="mt-1 text-sm text-slate-800">{formatDate(donor.last_donation)}</dd>
              </div>
            </dl>

            {isAdmin ? (
              <div className="mt-6 border-t border-slate-200 pt-5">
                <button
                  type="button"
                  onClick={() => setEditing((value) => !value)}
                  className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
                >
                  {editing ? "Cancel edit" : "Edit donor"}
                </button>
                {editing ? (
                  <form onSubmit={handleUpdate} className="mt-5 grid gap-4 sm:grid-cols-2">
                    <div className="sm:col-span-2">
                      <label htmlFor="edit-name" className="block text-sm font-medium">
                        Full name
                      </label>
                      <input
                        id="edit-name"
                        required
                        value={form.name}
                        onChange={(event) => setForm({ ...form, name: event.target.value })}
                        className={fieldClass}
                      />
                    </div>
                    <div>
                      <label htmlFor="edit-type" className="block text-sm font-medium">
                        Blood type
                      </label>
                      <select
                        id="edit-type"
                        value={form.blood_type}
                        onChange={(event) => setForm({ ...form, blood_type: event.target.value })}
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
                      <label htmlFor="edit-phone" className="block text-sm font-medium">
                        Phone
                      </label>
                      <input
                        id="edit-phone"
                        required
                        value={form.phone}
                        onChange={(event) => setForm({ ...form, phone: event.target.value })}
                        className={fieldClass}
                      />
                    </div>
                    <div className="sm:col-span-2">
                      <label htmlFor="edit-date" className="block text-sm font-medium">
                        Last donation
                      </label>
                      <input
                        id="edit-date"
                        type="date"
                        max={todayInputValue()}
                        value={form.last_donation ?? ""}
                        onChange={(event) =>
                          setForm({ ...form, last_donation: event.target.value || null })
                        }
                        className={fieldClass}
                      />
                    </div>
                    <div className="flex gap-2 sm:col-span-2">
                      <button
                        type="submit"
                        disabled={busy}
                        className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                      >
                        {busy ? "Saving…" : "Save changes"}
                      </button>
                      <button
                        type="button"
                        disabled={busy}
                        onClick={handleDelete}
                        className="rounded-lg border border-rose-300 px-4 py-2 text-sm font-semibold text-rose-700 disabled:opacity-50 hover:bg-rose-50"
                      >
                        Delete donor
                      </button>
                    </div>
                  </form>
                ) : null}
              </div>
            ) : null}
          </section>

          <aside className="space-y-5">
            <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
                Eligibility
              </h2>
              <div className="mt-3">
                <EligibilityBadge badge={donor.eligibility_badge} />
              </div>
              <p className="mt-4 text-sm leading-relaxed text-slate-700">{donor.eligibility_message}</p>
              <dl className="mt-5 space-y-3 border-t border-slate-100 pt-4 text-sm">
                <div className="flex justify-between gap-3">
                  <dt className="text-slate-500">Has history</dt>
                  <dd className="font-medium">{donor.has_donation_history ? "Yes" : "No"}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-slate-500">Days since donation</dt>
                  <dd className="font-medium">
                    {donor.days_since_last_donation === null ? "—" : pluralize(donor.days_since_last_donation, "day")}
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-slate-500">Days until eligible</dt>
                  <dd className="font-medium">{pluralize(donor.days_until_eligible, "day")}</dd>
                </div>
              </dl>
            </div>

            <Link
              href={`/requests/new?donor=${donor.id}`}
              className="block rounded-xl bg-rose-600 p-5 text-center text-sm font-semibold text-white hover:bg-rose-700"
            >
              Create a request with this donor →
            </Link>
            <p className="text-xs leading-relaxed text-slate-500">
              The server validates eligibility again when the request is submitted.
            </p>
          </aside>
        </div>
      ) : null}
    </AppShell>
  );
}
