"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { useAuth } from "@/components/AuthProvider";
import { AccessDeniedState, LoadingState } from "@/components/StateViews";
import type { Role } from "@/types";

export function ProtectedRoute({
  children,
  allowedRoles,
}: {
  children: ReactNode;
  allowedRoles?: Role[];
}) {
  const { profile, status } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (status === "unauthenticated") {
      const next = encodeURIComponent(pathname || "/");
      router.replace(`/login?next=${next}`);
    }
    if (status === "recovery") {
      router.replace("/auth/reset-password");
    }
  }, [status, pathname, router]);

  if (status === "loading") return <LoadingState label="Checking your session…" />;
  if (status === "unauthenticated") return <LoadingState label="Redirecting to sign in…" />;
  if (status === "recovery") return <LoadingState label="Redirecting to password reset…" />;
  if (!profile) return <AccessDeniedState />;
  if (allowedRoles && !allowedRoles.includes(profile.role)) return <AccessDeniedState />;

  return <>{children}</>;
}
