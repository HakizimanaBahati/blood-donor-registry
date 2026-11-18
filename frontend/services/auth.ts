import { apiRequest } from "@/lib/api";
import type { Profile } from "@/types";

export type DemoUser = "admin" | "hospital1" | "hospital2";

interface DevLoginResponse {
  access_token: string;
  role: "admin" | "hospital";
  user_id: string;
}

export function fetchProfile(token?: string | null): Promise<Profile> {
  return apiRequest<Profile>("/api/auth/me/", token === undefined ? {} : { token });
}

export async function devLogin(user: DemoUser): Promise<DevLoginResponse> {
  return apiRequest<DevLoginResponse>("/api/auth/dev-login/", {
    method: "POST",
    body: { user },
    skipAuth: true,
  });
}

export function requestLogout(): Promise<{ message: string }> {
  return apiRequest<{ message: string }>("/api/auth/logout/", { method: "POST" });
}
