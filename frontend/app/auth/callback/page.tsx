"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { useAuth } from "@/components/AuthProvider";
import { LoadingState } from "@/components/StateViews";
import { supabase } from "@/lib/supabase";

function safeCallbackMessage(errorCode: string | null, errorDescription: string | null): string {
  if (errorCode === "otp_expired") {
    return "This password recovery link is invalid or has expired. Request a new password reset email.";
  }
  if (errorCode === "access_denied") {
    return "This password recovery link could not be used. Request a new password reset email.";
  }
  if (errorDescription) {
    return "This password recovery link could not be used. Request a new password reset email.";
  }
  return "Unable to process the password recovery link. Request a new password reset email.";
}

function AuthCallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { status, markRecovery } = useAuth();
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function handleCallback() {
      const error = searchParams.get("error");
      const errorCode = searchParams.get("error_code");
      const errorDescription = searchParams.get("error_description");
      if (error || errorCode || errorDescription) {
        if (active) setMessage(safeCallbackMessage(errorCode, errorDescription));
        return;
      }

      const code = searchParams.get("code");
      if (code) {
        const { error: exchangeError } = await supabase.auth.exchangeCodeForSession(code);
        if (!active) return;
        if (exchangeError) {
          // detectSessionInUrl may have already exchanged the code; fall back to session check.
          const { data: existing } = await supabase.auth.getSession();
          if (!active) return;
          if (!existing.session) {
            setMessage("This password recovery link is invalid or has expired. Request a new password reset email.");
            return;
          }
        }
      }

      const { data, error: sessionError } = await supabase.auth.getSession();
      if (!active) return;
      if (sessionError || !data.session) {
        setMessage("Unable to establish a recovery session. Request a new password reset email.");
        return;
      }

      markRecovery();
      router.replace("/auth/reset-password");
    }

    void handleCallback();
    return () => {
      active = false;
    };
  }, [router, searchParams, markRecovery]);

  useEffect(() => {
    if (status === "recovery") {
      router.replace("/auth/reset-password");
    }
  }, [router, status]);

  if (message) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-10">
        <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h1 className="text-lg font-semibold text-slate-900">Password recovery</h1>
          <p className="mt-3 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700" role="alert">
            {message}
          </p>
          <button
            type="button"
            onClick={() => router.replace("/login")}
            className="mt-5 w-full rounded-lg bg-rose-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-rose-700"
          >
            Back to sign in
          </button>
        </div>
      </main>
    );
  }

  return <LoadingState label="Processing password recovery link…" />;
}

export default function AuthCallbackPage() {
  return (
    <Suspense fallback={<LoadingState label="Processing password recovery link…" />}>
      <AuthCallbackContent />
    </Suspense>
  );
}
