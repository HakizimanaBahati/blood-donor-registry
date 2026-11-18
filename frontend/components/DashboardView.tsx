"use client";

import Link from "next/link";

import { AppShell } from "@/components/AppShell";
import { BloodTypeChart } from "@/components/BloodTypeChart";
import { ErrorState, LoadingState } from "@/components/StateViews";
import { RequestTable } from "@/components/RequestTable";
import { useAsync } from "@/hooks/useAsync";
import { getDashboardSummary, getDonorsPerBloodType } from "@/services/analytics";
import type { Role } from "@/types";

function StatCard({ label, value, hint }: { label: string; value: number; hint?: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-2 text-3xl font-bold text-slate-900">{value}</p>
      {hint ? <p className="mt-1 text-xs text-slate-500">{hint}</p> : null}
    </div>
  );
}

export function DashboardView({ role }: { role: Role }) {
  const data = useAsync(
    async (signal) => {
      const [summary, counts] = await Promise.all([
        getDashboardSummary(signal),
        getDonorsPerBloodType(signal),
      ]);
      return { summary, counts };
    },
    [],
  );

  const isAdmin = role === "admin";

  return (
    <AppShell
      title={isAdmin ? "Registry overview" : "Hospital overview"}
      description={
        isAdmin
          ? "A server-verified view of donors, hospitals and blood requests."
          : "Your hospital’s requests and the current donor pool."
      }
      actions={
        <>
          <Link
            href="/requests/new"
            className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-700"
          >
            New request
          </Link>
          <Link
            href="/donors"
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
          >
            Browse donors
          </Link>
          {isAdmin ? (
            <Link
              href="/donors/new"
              className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
            >
              Add donor
            </Link>
          ) : null}
        </>
      }
    >
      {data.loading ? <LoadingState label="Loading dashboard…" /> : null}
      {data.error ? <ErrorState message={data.error} onRetry={data.reload} /> : null}

      {data.data ? (
        <div className="space-y-6">
          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Total donors" value={data.data.summary.total_donors} />
            <StatCard
              label="Eligible donors"
              value={data.data.summary.eligible_donors}
              hint="Server checked against the 90-day rule"
            />
            <StatCard label="Ineligible donors" value={data.data.summary.ineligible_donors} />
            <StatCard
              label={isAdmin ? "Requests" : "Your requests"}
              value={data.data.summary.total_requests}
            />
          </section>

          {isAdmin ? (
            <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard label="Hospitals" value={data.data.summary.total_hospitals} />
            </section>
          ) : null}

          <section className="grid gap-6 lg:grid-cols-5">
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-3">
              <div className="mb-3 flex items-center justify-between">
                <div>
                  <h2 className="text-base font-semibold">Donors by blood type</h2>
                  <p className="text-xs text-slate-500">Counts calculated from the database.</p>
                </div>
                <Link href="/analytics" className="text-sm font-semibold text-rose-600 hover:underline">
                  Details →
                </Link>
              </div>
              <BloodTypeChart data={data.data.counts} />
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-2">
              <h2 className="text-base font-semibold">Quick actions</h2>
              <ul className="mt-3 space-y-2 text-sm">
                <li>
                  <Link href="/requests/new" className="text-rose-700 hover:underline">
                    Create a blood request →
                  </Link>
                </li>
                <li>
                  <Link href="/donors?eligible=true" className="text-rose-700 hover:underline">
                    Find eligible donors →
                  </Link>
                </li>
                <li>
                  <Link href="/requests" className="text-rose-700 hover:underline">
                    Review request history →
                  </Link>
                </li>
                {isAdmin ? (
                  <li>
                    <Link href="/hospitals" className="text-rose-700 hover:underline">
                      Manage hospitals →
                    </Link>
                  </li>
                ) : null}
              </ul>
              <p className="mt-5 rounded-lg bg-slate-50 p-3 text-xs leading-relaxed text-slate-500">
                The API re-checks eligibility when a donor is attached to a request. Ineligible
                donors are rejected with HTTP 400.
              </p>
            </div>
          </section>

          <section>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-base font-semibold">Recent requests</h2>
              <Link href="/requests" className="text-sm font-semibold text-rose-600 hover:underline">
                View all →
              </Link>
            </div>
            {data.data.summary.recent_requests.length ? (
              <RequestTable requests={data.data.summary.recent_requests} />
            ) : (
              <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
                No requests have been created yet.
              </div>
            )}
          </section>
        </div>
      ) : null}
    </AppShell>
  );
}
