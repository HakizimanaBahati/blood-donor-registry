"use client";

import { createClient } from "@supabase/supabase-js";

import { DEV_TOKEN_KEY } from "@/lib/constants";

// Placeholders keep the app renderable without a Supabase project. Real Auth
// only works when both public environment variables are configured.
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "http://localhost:54321";
// Supabase's newer publishable key (sb_publishable_...) replaces the legacy anon key.
// Support both names so existing .env files keep working.
const supabaseAnonKey =
  process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ||
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ||
  "local-anon-key-placeholder";

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
  },
});

export function isDevLoginEnabled(): boolean {
  return process.env.NEXT_PUBLIC_ALLOW_DEV_LOGIN === "true";
}

export function setDevToken(token: string): void {
  window.sessionStorage.setItem(DEV_TOKEN_KEY, token);
}

export function clearDevToken(): void {
  window.sessionStorage.removeItem(DEV_TOKEN_KEY);
}

export function hasDevToken(): boolean {
  return typeof window !== "undefined" && Boolean(window.sessionStorage.getItem(DEV_TOKEN_KEY));
}

/** Returns the development token first, then the real Supabase access token. */
export async function getAccessToken(): Promise<string | null> {
  if (typeof window === "undefined") return null;

  if (isDevLoginEnabled()) {
    const devToken = window.sessionStorage.getItem(DEV_TOKEN_KEY);
    if (devToken) return devToken;
  }

  try {
    const { data, error } = await supabase.auth.getSession();
    if (error || !data.session?.access_token) return null;
    return data.session.access_token;
  } catch {
    return null;
  }
}
