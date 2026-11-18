"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { DonorTable } from "@/components/DonorTable";
import { Pagination } from "@/components/Pagination";
import { useAuth } from "@/components/AuthProvider";
import { EmptyState, ErrorState, LoadingState } from "@/components/StateViews";
import { useAsync } from "@/hooks/useAsync";
import { BLOOD_TYPES } from "@/lib/constants";
import { listDonors } from "@/services/donors";

const PAGE_SIZE = 10;

const ORDERING_OPTIONS = [
  { value: "name", label: "Name (A–Z)" },
  { value: "-name", label: "Name (Z–A)" },
  { value: "blood_type", label: "Blood type (A–Z)" },
  { value: "-eligibility", label: "Eligibility first" },
  { value: "eligibility", label: "Ineligible first" },
  { value: "-last_donation", label: "Recent donation first" },
  { value: "-created_at", label: "Newly registered first" },
];

function DonorsContent() {
  const searchParams = useSearchParams();
  const { profile } = useAuth();
  const isAdmin = profile?.role === "admin";

  const initialEligible = searchParams.get("eligible");
  const [searchInput, setSearchInput] = useState(searchParams.get("search") ?? "");
  const [search, setSearch] = useState(searchParams.get("search") ?? "");
  const [bloodType, setBloodType] = useState(searchParams.get("blood_type") ?? "");
  const [eligible, setEligible] = useState<boolean | null>(
    initialEligible === "true" ? true : initialEligible === "false" ? false : null,
  );
  const [ordering, setOrdering] = useState("name");
  const [page, setPage] = useState(1);

  useEffect(() => {
    const timer = window.setTimeout(() => setSearch(searchInput.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    setPage(1);
  }, [search, bloodType, eligible, ordering]);

  const query = useMemo(
    () => ({ page, pageSize: PAGE_SIZE, search, bloodType, eligible, ordering }),
    [page, search, bloodType, eligible, ordering],
  );

  const result = useAsync((signal) => listDonors(query, signal), [query]);

  const pageCount = result.data ? Math.ceil(result.data.count / PAGE_SIZE) : 1;
  const hasFilters = Boolean(search || bloodType || eligible !== null);

  return (
    <AppShell
      title="Donors"
      description="Search the registry and review server-computed eligibility. Contact details for ineligible donors are hidden from hospital staff."
      actions={
        isAdmin ? (
          <Link
            href="/donors/new"
            className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-700"
          >
            Add donor
          </Link>
        ) : null
      }
    >
      <section className="mb-6 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="grid gap-3 md:grid-cols-4">
          <div className="md:col-span-2">
            <label htmlFor="donor-search" className="block text-xs font-semibold text-slate-600">
              Search name {isAdmin ? "or phone" : ""}
            </label>
            <input
              id="donor-search"
              type="search"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="Start typing…"
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label htmlFor="blood-type" className="block text-xs font-semibold text-slate-600">
              Blood type
            </label>
            <select
              id="blood-type"
              value={bloodType}
              onChange={(event) => setBloodType(event.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
            >
              <option value="">All types</option>
              {BLOOD_TYPES.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="eligible" className="block text-xs font-semibold text-slate-600">
              Eligibility
            </label>
            <select
              id="eligible"
              value={eligible === null ? "" : eligible ? "true" : "false"}
              onChange={(event) =>
                setEligible(event.target.value === "" ? null : event.target.value === "true")
              }
              className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
            >
              <option value="">Any</option>
              <option value="true">Eligible only</option>
              <option value="false">Not eligible</option>
            </select>
          </div>
          <div className="md:col-span-1">
            <label htmlFor="ordering" className="block text-xs font-semibold text-slate-600">
              Sort by
            </label>
            <select
              id="ordering"
              value={ordering}
              onChange={(event) => setOrdering(event.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
            >
              {ORDERING_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </section>

      {result.loading ? <LoadingState label="Loading donors…" /> : null}
      {result.error ? <ErrorState message={result.error} onRetry={result.reload} /> : null}

      {!result.loading && !result.error && result.data ? (
        <div className="space-y-5">
          <p className="text-sm text-slate-500">
            {result.data.count} donor{result.data.count === 1 ? "" : "s"} found
            {hasFilters ? " with the current filters" : ""}.
          </p>
          {result.data.results.length ? (
            <DonorTable donors={result.data.results} />
          ) : (
            <EmptyState
              title="No donors match these filters"
              description="Try a different blood type, clear the search, or change the eligibility filter."
            />
          )}
          <Pagination
            page={page}
            pageCount={pageCount}
            total={result.data.count}
            onChange={setPage}
          />
        </div>
      ) : null}
    </AppShell>
  );
}

export default function DonorsPage() {
  return (
    <Suspense fallback={<LoadingState label="Loading donor registry…" />}>
      <DonorsContent />
    </Suspense>
  );
}
