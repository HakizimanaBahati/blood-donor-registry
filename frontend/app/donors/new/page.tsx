"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";

import { AppShell } from "@/components/AppShell";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { ErrorState, SuccessBanner } from "@/components/StateViews";
import { errorMessage } from "@/lib/errors";
import { BLOOD_TYPES } from "@/lib/constants";
import { todayInputValue } from "@/lib/format";
import { createDonor } from "@/services/donors";
import type { Donor } from "@/types";

const fieldClass = "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-rose-500";
const emptyForm = { name: "", blood_type: "A+", phone: "", last_donation: "" };

export default function NewDonorPage() {
  const [form, setForm] = useState(emptyForm);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<Donor | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setCreated(null);
    try {
      const donor = await createDonor({
        name: form.name,
        blood_type: form.blood_type,
        phone: form.phone,
        last_donation: form.last_donation || null,
      });
      setCreated(donor);
      setForm(emptyForm);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  return (
    <ProtectedRoute allowedRoles={["admin"]}>
      <AppShell
        title="Add donor"
        description="Register a new donor. Eligibility is calculated by the server from the last donation date."
        actions={
          <Link
            href="/donors"
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
          >
            ← Back to donors
          </Link>
        }
      >
        <div className="mx-auto max-w-2xl space-y-5">
          {created ? (
            <SuccessBanner>
              <p className="font-semibold">{created.name} was added to the registry.</p>
              <p className="mt-1">
                Eligibility: <span className="capitalize">{created.eligibility_badge.replace("_", " ")}</span>.{" "}
                <Link href={`/donors/${created.id}`} className="underline">
                  View donor
                </Link>{" "}
                ·{" "}
                <button type="button" onClick={() => setCreated(null)} className="underline">
                  Add another
                </button>
              </p>
            </SuccessBanner>
          ) : null}

          {error ? <ErrorState title="Registration failed" message={error} /> : null}

          <form
            onSubmit={handleSubmit}
            className="space-y-5 rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
          >
            <div>
              <label htmlFor="name" className="block text-sm font-medium text-slate-700">
                Full name
              </label>
              <input
                id="name"
                required
                minLength={2}
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
                className={fieldClass}
                placeholder="e.g. Jordan Lee"
              />
            </div>

            <div className="grid gap-5 sm:grid-cols-2">
              <div>
                <label htmlFor="blood_type" className="block text-sm font-medium text-slate-700">
                  Blood type
                </label>
                <select
                  id="blood_type"
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
                <label htmlFor="phone" className="block text-sm font-medium text-slate-700">
                  Phone
                </label>
                <input
                  id="phone"
                  type="tel"
                  required
                  value={form.phone}
                  onChange={(event) => setForm({ ...form, phone: event.target.value })}
                  className={fieldClass}
                  placeholder="+1 555 010 1234"
                />
                <p className="mt-1 text-xs text-slate-500">Must be unique across the registry.</p>
              </div>
            </div>

            <div>
              <label htmlFor="last_donation" className="block text-sm font-medium text-slate-700">
                Last donation <span className="font-normal text-slate-400">(optional)</span>
              </label>
              <input
                id="last_donation"
                type="date"
                max={todayInputValue()}
                value={form.last_donation}
                onChange={(event) => setForm({ ...form, last_donation: event.target.value })}
                className={fieldClass}
              />
              <p className="mt-1 text-xs text-slate-500">
                Leave empty for a new donor with no recorded donation history.
              </p>
            </div>

            <button
              type="submit"
              disabled={busy}
              className="w-full rounded-lg bg-rose-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-rose-700 disabled:opacity-50"
            >
              {busy ? "Saving…" : "Add donor"}
            </button>
          </form>
        </div>
      </AppShell>
    </ProtectedRoute>
  );
}
