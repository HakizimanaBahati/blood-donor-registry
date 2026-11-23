"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { useAuth } from "@/components/AuthProvider";
import { LoadingState } from "@/components/StateViews";
import { dashboardPath } from "@/lib/navigation";
import { supabase } from "@/lib/supabase";

function isSafePassword(password: string): string | null {
  if (password.length < 8) return "Password must be at least 8 characters long.";
  return null;
}

export default function ResetPasswordPage() {
  const router = useRouter();
  const { status, profile, completeRecovery, signOut } = useAuth();
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [sessionChecked, setSessionChecked] = useState(false);
  const [hasRecoverySession, setHasRecoverySession] = useState(false);

  useEffect(() => {
    let active = true;

    async function verifyRecoverySession() {
      if (status === "loading") return;
      if (status === "recovery") {
        if (active) {
          setHasRecoverySession(true);
          setSessionChecked(true);
        }
        return;
      }

      // If the provider hasn't marked recovery, only allow when a Supabase session exists
      // and the user reached this page through the recovery flow. We avoid exposing normal
      // authenticated access by requiring explicit recovery status; fallback checks session
      // only to avoid false negatives during event timing.
      const { data, error: sessionError } = await supabase.auth.getSession();
      if (!active) return;
      if (sessionError || !data.session) {
        setHasRecoverySession(false);
        setSessionChecked(true);
        return;
      }

      // Session exists but provider doesn't report recovery - treat as not allowed.
      setHasRecoverySession(false);
      setSessionChecked(true);
    }

    void verifyRecoverySession();
    return () => {
      active = false;
    };
  }, [status]);

  useEffect(() => {
    if (!sessionChecked) return;
    if (hasRecoverySession) return;
    if (status === "authenticated" && profile) {
      router.replace(dashboardPath(profile.role));
      return;
    }
    if (status === "unauthenticated") {
      router.replace("/login");
    }
  }, [hasRecoverySession, profile, router, sessionChecked, status]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSuccess(null);

    const passwordError = isSafePassword(password);
    if (passwordError) {
      setError(passwordError);
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setBusy(true);
    try {
      const { data: sessionData, error: sessionError } = await supabase.auth.getSession();
      if (sessionError || !sessionData.session) {
        setError("Your recovery session is invalid or has expired. Request a new password reset email.");
        return;
      }

      const { error: updateError } = await supabase.auth.updateUser({ password });
      if (updateError) {
        setError("Unable to update your password. Please request a new recovery link and try again.");
        return;
      }

      setSuccess("Password updated successfully. Redirecting…");
      const nextProfile = await completeRecovery();
      if (nextProfile) {
        router.replace(dashboardPath(nextProfile.role));
        return;
      }

      // If profile cannot be resolved, sign out safely rather than leaving an ambiguous session.
      await signOut();
      router.replace("/login");
    } catch {
      setError("Unable to update your password. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  if (status === "loading" || !sessionChecked) {
    return <LoadingState label="Checking recovery session…" />;
  }

  if (!hasRecoverySession) {
    return <LoadingState label="Redirecting…" />;
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-10">
      <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <h1 className="text-xl font-semibold text-slate-900">Set a new password</h1>
        <p className="mt-2 text-sm text-slate-500">
          Choose a new password for your account. After updating it, you&apos;ll be redirected to your dashboard.
        </p>

        {error ? (
          <p className="mt-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700" role="alert">
            {error}
          </p>
        ) : null}
        {success ? (
          <p className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700" role="status">
            {success}
          </p>
        ) : null}

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label htmlFor="new-password" className="block text-sm font-medium text-slate-700">
              New password
            </label>
            <input
              id="new-password"
              type="password"
              required
              minLength={8}
              autoComplete="new-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-rose-500"
              placeholder="At least 8 characters"
            />
          </div>
          <div>
            <label htmlFor="confirm-password" className="block text-sm font-medium text-slate-700">
              Confirm new password
            </label>
            <input
              id="confirm-password"
              type="password"
              required
              minLength={8}
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-rose-500"
              placeholder="Re-enter your new password"
            />
          </div>
          <button
            type="submit"
            disabled={busy || Boolean(success)}
            className="w-full rounded-lg bg-rose-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-rose-700 disabled:opacity-50"
          >
            {busy ? "Updating password…" : "Update password"}
          </button>
        </form>

        <button
          type="button"
          onClick={() => {
            void signOut().then(() => router.replace("/login"));
          }}
          className="mt-4 w-full text-sm font-medium text-slate-500 hover:text-slate-700"
        >
          Cancel and return to sign in
        </button>
      </div>
    </main>
  );
}
