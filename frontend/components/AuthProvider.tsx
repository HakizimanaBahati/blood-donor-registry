"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { ApiError } from "@/lib/api";
import { clearDevToken, getAccessToken, setDevToken, supabase } from "@/lib/supabase";
import { devLogin, fetchProfile, requestLogout, type DemoUser } from "@/services/auth";
import type { Profile } from "@/types";

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

interface AuthContextValue {
  profile: Profile | null;
  status: AuthStatus;
  error: string | null;
  signInWithPassword: (email: string, password: string) => Promise<Profile | null>;
  signInWithDemo: (user: DemoUser) => Promise<Profile | null>;
  signOut: () => Promise<void>;
  refresh: () => Promise<Profile | null>;
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

  const refresh = useCallback(async (explicitToken?: string | null): Promise<Profile | null> => {
    setError(null);
    try {
      const token = explicitToken !== undefined ? explicitToken : await getAccessToken();
      if (!token) {
        setProfile(null);
        setStatus("unauthenticated");
        return null;
      }
      const result = await fetchProfile(token);
      setProfile(result);
      setStatus("authenticated");
      return result;
    } catch (reason) {
      setProfile(null);
      setStatus("unauthenticated");
      setError(messageOf(reason));
      return null;
    }
  }, []);

  useEffect(() => {
    void refresh();

    const { data } = supabase.auth.onAuthStateChange((event) => {
      if (event === "SIGNED_OUT") {
        clearDevToken();
        setProfile(null);
        setStatus("unauthenticated");
        return;
      }
      if (event === "SIGNED_IN" || event === "TOKEN_REFRESHED") void refresh();
    });

    return () => data.subscription.unsubscribe();
  }, [refresh]);

  const signInWithPassword = useCallback(
    async (email: string, password: string): Promise<Profile | null> => {
      setError(null);
      clearDevToken();
      const { error: authError } = await supabase.auth.signInWithPassword({ email, password });
      if (authError) {
        setError(authError.message);
        return null;
      }
      return refresh();
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

  const signOut = useCallback(async () => {
    try {
      await requestLogout();
    } catch {
      // Django is stateless; discarding the token below is what actually signs out.
    }
    clearDevToken();
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
    }),
    [profile, status, error, signInWithPassword, signInWithDemo, signOut, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
