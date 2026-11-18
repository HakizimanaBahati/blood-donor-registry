"use client";

import Link from "next/link";
import { useState } from "react";

import { AppShell } from "@/components/AppShell";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { EmptyState, ErrorState, LoadingState } from "@/components/StateViews";
import { Pagination } from "@/components/Pagination";
import { RequestTable } from "@/components/RequestTable";
import { useAsync } from "@/hooks/useAsync";
import { listRequests } from "@/services/requests";

const PAGE_SIZE = 10;

function RequestsContent() {
  const [page, setPage] = useState(1);
  const result = useAsync((signal) => listRequests({ page, pageSize: PAGE_SIZE }, signal), [page]);
  const pageCount = result.data ? Math.ceil(result.data.count / PAGE_SIZE) : 1;

  return (
    <AppShell
      title="Blood requests"
      description="Admins see all requests; hospital accounts only see requests belonging to their own hospital."
      actions={
        <Link
          href="/requests/new"
          className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-700"
        >
          New request
        </Link>
      }
    >
      {result.loading ? <LoadingState label="Loading requests…" /> : null}
      {result.error ? <ErrorState message={result.error} onRetry={result.reload} /> : null}

      {!result.loading && !result.error && result.data ? (
        <div className="space-y-5">
          <p className="text-sm text-slate-500">{result.data.count} request(s) in scope.</p>
          {result.data.results.length ? (
            <RequestTable requests={result.data.results} />
          ) : (
            <EmptyState
              title="No requests yet"
              description="Create the first blood request for your hospital."
              action={
                <Link
                  href="/requests/new"
                  className="inline-block rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-700"
                >
                  New request
                </Link>
              }
            />
          )}
          <Pagination page={page} pageCount={pageCount} total={result.data.count} onChange={setPage} />
        </div>
      ) : null}
    </AppShell>
  );
}

export default function RequestsPage() {
  return (
    <ProtectedRoute>
      <RequestsContent />
    </ProtectedRoute>
  );
}
