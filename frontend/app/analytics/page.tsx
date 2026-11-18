"use client";

import { ProtectedRoute } from "@/components/ProtectedRoute";
import { AppShell } from "@/components/AppShell";
import { BloodTypeChart } from "@/components/BloodTypeChart";
import { ErrorState, LoadingState } from "@/components/StateViews";
import { useAsync } from "@/hooks/useAsync";
import { getDashboardSummary, getDonorsPerBloodType } from "@/services/analytics";
import { BLOOD_TYPES } from "@/lib/constants";

function AnalyticsContent() {
  const result = useAsync(
    async (signal) => {
      const [counts, summary] = await Promise.all([
        getDonorsPerBloodType(signal),
        getDashboardSummary(signal),
      ]);
      return { counts, summary };
    },
    [],
  );

  const data = result.data;
  const total = data
    ? BLOOD_TYPES.reduce((sum, type) => sum + (data.counts[type] ?? 0), 0)
    : 0;

  return (
    <AppShell
      title="Analytics"
      description="Counts come directly from the API; the browser does not calculate eligibility."
    >
      {result.loading ? <LoadingState label="Loading analytics…" /> : null}
      {result.error ? <ErrorState message={result.error} onRetry={result.reload} /> : null}

      {data ? (
        <div className="grid gap-6 lg:grid-cols-5">
          <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-3">
            <h2 className="text-base font-semibold">Donors by blood type</h2>
            <p className="text-xs text-slate-500">All eight blood types are shown, including zero counts.</p>
            <div className="mt-4">
              <BloodTypeChart data={data.counts} />
            </div>
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-2">
            <h2 className="text-base font-semibold">Breakdown</h2>
            <table className="mt-4 w-full text-sm">
              <thead className="text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="pb-2">Type</th>
                  <th className="pb-2 text-right">Donors</th>
                  <th className="pb-2 text-right">Share</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {BLOOD_TYPES.map((type) => {
                  const count = data.counts[type] ?? 0;
                  return (
                    <tr key={type}>
                      <td className="py-2 font-semibold text-rose-700">{type}</td>
                      <td className="py-2 text-right">{count}</td>
                      <td className="py-2 text-right text-slate-500">
                        {total ? `${Math.round((count / total) * 100)}%` : "0%"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </section>

          <section className="grid gap-4 sm:grid-cols-3 lg:col-span-5">
            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <p className="text-xs uppercase text-slate-500">Eligible donors</p>
              <p className="mt-2 text-2xl font-bold">{data.summary.eligible_donors}</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <p className="text-xs uppercase text-slate-500">Ineligible donors</p>
              <p className="mt-2 text-2xl font-bold">{data.summary.ineligible_donors}</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <p className="text-xs uppercase text-slate-500">Requests in scope</p>
              <p className="mt-2 text-2xl font-bold">{data.summary.total_requests}</p>
            </div>
          </section>
        </div>
      ) : null}
    </AppShell>
  );
}

export default function AnalyticsPage() {
  return (
    <ProtectedRoute>
      <AnalyticsContent />
    </ProtectedRoute>
  );
}
