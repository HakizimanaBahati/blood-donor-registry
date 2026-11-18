import type { Role } from "@/types";

export function dashboardPath(role: Role | null | undefined): string {
  return role === "admin" ? "/admin/dashboard" : "/hospital/dashboard";
}
