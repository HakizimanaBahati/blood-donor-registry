"use client";

import { AlertTriangle, CheckCircle2, Inbox, Loader2, RotateCcw } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

const shell = "rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm";

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div className={shell} role="status" aria-live="polite">
      <Loader2 className="mx-auto h-7 w-7 animate-spin text-rose-600" aria-hidden="true" />
      <p className="mt-3 text-sm font-medium text-slate-600">{label}</p>
    </div>
  );
}

export function EmptyState({
  title = "Nothing here yet",
  description,
  action,
}: {
  title?: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className={shell}>
      <Inbox className="mx-auto h-8 w-8 text-slate-400" aria-hidden="true" />
      <h3 className="mt-3 text-base font-semibold text-slate-800">{title}</h3>
      {description ? <p className="mx-auto mt-1 max-w-md text-sm text-slate-500">{description}</p> : null}
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
  title = "We couldn’t load this",
}: {
  message: string;
  onRetry?: () => void;
  title?: string;
}) {
  return (
    <div className={`${shell} border-rose-200 bg-rose-50/60`} role="alert">
      <AlertTriangle className="mx-auto h-8 w-8 text-rose-600" aria-hidden="true" />
      <h3 className="mt-3 text-base font-semibold text-rose-900">{title}</h3>
      <p className="mx-auto mt-1 max-w-md text-sm text-rose-700">{message}</p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-5 inline-flex items-center gap-2 rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-700"
        >
          <RotateCcw className="h-4 w-4" aria-hidden="true" /> Try again
        </button>
      ) : null}
    </div>
  );
}

export function SuccessBanner({ children }: { children: ReactNode }) {
  return (
    <div
      className="flex items-start gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800"
      role="status"
    >
      <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
      <div>{children}</div>
    </div>
  );
}

export function AccessDeniedState() {
  return (
    <div className={shell}>
      <AlertTriangle className="mx-auto h-8 w-8 text-amber-600" aria-hidden="true" />
      <h3 className="mt-3 text-base font-semibold text-slate-800">Access denied</h3>
      <p className="mx-auto mt-1 max-w-md text-sm text-slate-500">
        Your account does not have permission to view this page.
      </p>
      <Link
        href="/profile"
        className="mt-5 inline-block rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700"
      >
        Back to profile
      </Link>
    </div>
  );
}
