"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { ApiError } from "@/lib/api";
import { clearDevToken, getAccessToken, setDevToken, supabase } from "@/lib/supabase";
import { devLogin, fetchProfile, requestLogout, type DemoUser } from "@/services/auth";
import type { Profile } from "@/types";

type AuthStatus = "loading" | "authenticated" | "unauthenticated" | "recovery";

interface AuthContextValue {
  profile: Profile | null;
  status: AuthStatus;
  error: string | null;
  signInWithPassword: (email: string, password: string) => Promise<Profile | null>;
  signInWithDemo: (user: DemoUser) => Promise<Profile | null>;
  signOut: () => Promise<void>;
  refresh: (explicitToken?: string | null) => Promise<Profile | null>;
  completeRecovery: () => Promise<Profile | null>;
  markRecovery: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function messageOf(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "Authentication failed. Please try again.";
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [error, setError] = useState<string | null>(null);
  const refreshSeq = useRef(0);
  const recoveryRef = useRef(false);

  const refresh = useCallback(async (explicitToken?: string | null): Promise<Profile | null> => {
    const seq = ++refreshSeq.current;
    setError(null);
    try {
      const token = explicitToken !== undefined ? explicitToken : await getAccessToken();
      if (seq !== refreshSeq.current) return null;
      if (!token) {
        setProfile(null);
        setStatus(recoveryRef.current ? "recovery" : "unauthenticated");
        return null;
      }
      if (recoveryRef.current) {
        setProfile(null);
        setStatus("recovery");
        return null;
      }
      const result = await fetchProfile(token);
      if (seq !== refreshSeq.current) return null;
      recoveryRef.current = false;
      setProfile(result);
      setStatus("authenticated");
      return result;
    } catch (reason) {
      if (seq !== refreshSeq.current) return null;
      setProfile(null);
      setStatus("unauthenticated");
      setError(messageOf(reason));
      return null;
    }
  }, []);

  useEffect(() => {
    void refresh();

    const { data } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === "PASSWORD_RECOVERY") {
        recoveryRef.current = true;
        setProfile(null);
        setStatus("recovery");
        setError(null);
        return;
      }
      if (event === "SIGNED_OUT") {
        clearDevToken();
        recoveryRef.current = false;
        setProfile(null);
        setStatus("unauthenticated");
        return;
      }
      if (event === "SIGNED_IN" || event === "TOKEN_REFRESHED") {
        if (recoveryRef.current) {
          setProfile(null);
          setStatus("recovery");
          return;
        }
        const accessToken = session?.access_token ?? null;
        void refresh(accessToken ?? undefined);
      }
    });

    return () => data.subscription.unsubscribe();
  }, [refresh]);

  const signInWithPassword = useCallback(
    async (email: string, password: string): Promise<Profile | null> => {
      setError(null);
      clearDevToken();
      const { data, error: authError } = await supabase.auth.signInWithPassword({ email, password });
      if (authError) {
        setError(authError.message);
        return null;
      }
      const accessToken = data.session?.access_token ?? null;
      if (!accessToken) {
        setProfile(null);
        setStatus("unauthenticated");
        setError("Sign-in succeeded but no access token was returned. Please try again.");
        return null;
      }
      return refresh(accessToken);
    },
    [refresh],
  );

  const signInWithDemo = useCallback(
    async (user: DemoUser): Promise<Profile | null> => {
      setError(null);
      try {
        const result = await devLogin(user);
        setDevToken(result.access_token);
        return await refresh(result.access_token);
      } catch (reason) {
        setError(messageOf(reason));
        return null;
      }
    },
    [refresh],
  );

  const markRecovery = useCallback(() => {
    refreshSeq.current += 1;
    recoveryRef.current = true;
    setProfile(null);
    setError(null);
    setStatus("recovery");
  }, []);

  const completeRecovery = useCallback(async (): Promise<Profile | null> => {
    recoveryRef.current = false;
    return refresh();
  }, [refresh]);

  const signOut = useCallback(async () => {
    try {
      await requestLogout();
    } catch {
      // Django is stateless; discarding the token below is what actually signs out.
    }
    clearDevToken();
    recoveryRef.current = false;
    await supabase.auth.signOut();
    setProfile(null);
    setStatus("unauthenticated");
    setError(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      profile,
      status,
      error,
      signInWithPassword,
      signInWithDemo,
      signOut,
      refresh,
      completeRecovery,
      markRecovery,
    }),
    [profile, status, error, signInWithPassword, signInWithDemo, signOut, refresh, completeRecovery, markRecovery],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
