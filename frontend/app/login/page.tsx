"use client";

import { Droplets, ShieldCheck } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState, type FormEvent } from "react";

import { useAuth } from "@/components/AuthProvider";
import { LoadingState } from "@/components/StateViews";
import { dashboardPath } from "@/lib/navigation";
import { isDevLoginEnabled } from "@/lib/supabase";
import type { DemoUser } from "@/services/auth";
import type { Role } from "@/types";

const DEMO_USERS: { key: DemoUser; label: string; hint: string }[] = [
  { key: "admin", label: "Administrator", hint: "Full access · manages donors and hospitals" },
  { key: "hospital1", label: "Hospital A", hint: "Sees only its own requests" },
  { key: "hospital2", label: "Hospital B", hint: "Separate hospital scope" },
];

function safeDestination(next: string | null, role: Role): string {
  if (next && next.startsWith("/") && !next.startsWith("//")) return next;
  return dashboardPath(role);
}

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const nextPath = searchParams.get("next");
  const { profile, status, error, signInWithPassword, signInWithDemo } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);

  useEffect(() => {
    if (status === "authenticated" && profile) {
      router.replace(safeDestination(nextPath, profile.role));
    }
  }, [status, profile, nextPath, router]);

  async function handlePasswordSignIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy("password");
    setLocalError(null);
    const result = await signInWithPassword(email, password);
    setBusy(null);
    if (!result) setLocalError("Sign-in failed. Check your email and password.");
  }

  async function handleDemoSignIn(user: DemoUser) {
    setBusy(user);
    setLocalError(null);
    const result = await signInWithDemo(user);
    setBusy(null);
    if (!result) setLocalError("Demo sign-in failed. Is the Django server running with DEBUG enabled?");
  }

  const showError = localError ?? error;

  return (
    <main className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-50 via-white to-rose-50 px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 flex items-center justify-center gap-3">
          <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-rose-600 text-white shadow-lg shadow-rose-200">
            <Droplets className="h-6 w-6" aria-hidden="true" />
          </span>
          <div>
            <h1 className="text-xl font-bold">Blood Donor Registry</h1>
            <p className="text-xs text-slate-500">Secure coordination portal</p>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
          <h2 className="text-lg font-semibold">Sign in</h2>
          <p className="mt-1 text-sm text-slate-500">
            Use your Supabase account. Roles and permissions are resolved by the API.
          </p>

          {status === "loading" ? (
            <div className="mt-4">
              <LoadingState label="Checking your session…" />
            </div>
          ) : null}

          {showError ? (
            <div className="mt-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700" role="alert">
              {showError}
            </div>
          ) : null}

          <form onSubmit={handlePasswordSignIn} className="mt-6 space-y-4">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-slate-700">
                Email
              </label>
              <input
                id="email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-rose-500"
                placeholder="you@example.com"
              />
            </div>
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-slate-700">
                Password
              </label>
              <input
                id="password"
                type="password"
                required
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-rose-500"
                placeholder="••••••••"
              />
            </div>
            <button
              type="submit"
              disabled={Boolean(busy)}
              className="w-full rounded-lg bg-rose-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-rose-700 disabled:opacity-50"
            >
              {busy === "password" ? "Signing in…" : "Sign in with Supabase"}
            </button>
          </form>

          {isDevLoginEnabled() ? (
            <div className="mt-7 border-t border-slate-200 pt-6">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                <ShieldCheck className="h-4 w-4" aria-hidden="true" />
                Offline demo accounts
              </div>
              <p className="mt-2 text-xs text-slate-500">
                Development only. These buttons call the local Django dev-login endpoint; real
                deployments must use Supabase Auth.
              </p>
              <div className="mt-3 space-y-2">
                {DEMO_USERS.map((demo) => (
                  <button
                    key={demo.key}
                    type="button"
                    disabled={Boolean(busy)}
                    onClick={() => handleDemoSignIn(demo.key)}
                    className="flex w-full items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-left hover:border-rose-300 hover:bg-rose-50/60 disabled:opacity-50"
                  >
                    <span>
                      <span className="block text-sm font-semibold text-slate-800">{demo.label}</span>
                      <span className="block text-xs text-slate-500">{demo.hint}</span>
                    </span>
                    <span className="text-xs font-semibold text-rose-600">
                      {busy === demo.key ? "…" : "Enter →"}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          ) : null}
        </div>

        <p className="mt-5 text-center text-xs text-slate-400">
          Donor eligibility is always decided server-side. This portal never trusts a client flag.
        </p>
      </div>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<LoadingState label="Preparing sign in…" />}>
      <LoginForm />
    </Suspense>
  );
}
