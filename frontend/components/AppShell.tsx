"use client";

import { Droplets, LogOut } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";

import { useAuth } from "@/components/AuthProvider";
import { initials } from "@/lib/format";
import type { Role } from "@/types";

interface NavItem {
  href: string;
  label: string;
}

const SHARED: NavItem[] = [
  { href: "/donors", label: "Donors" },
  { href: "/requests", label: "Requests" },
  { href: "/analytics", label: "Analytics" },
  { href: "/profile", label: "Profile" },
];

const NAV: Record<Role, NavItem[]> = {
  admin: [
    { href: "/admin/dashboard", label: "Overview" },
    ...SHARED,
    { href: "/hospitals", label: "Hospitals" },
  ],
  hospital: [
    { href: "/hospital/dashboard", label: "Overview" },
    { href: "/requests/new", label: "New request" },
    ...SHARED,
  ],
};

export function AppShell({
  title,
  description,
  actions,
  children,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  const { profile, signOut } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const items = profile ? NAV[profile.role] : [];

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <Link href={profile?.role === "admin" ? "/admin/dashboard" : "/hospital/dashboard"} className="flex items-center gap-2">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-rose-600 text-white">
              <Droplets className="h-5 w-5" aria-hidden="true" />
            </span>
            <span>
              <span className="block text-sm font-bold leading-tight">Blood Donor Registry</span>
              <span className="block text-xs text-slate-500">Secure donor coordination</span>
            </span>
          </Link>
          <div className="flex items-center gap-3">
            <div className="hidden text-right sm:block">
              <p className="text-sm font-semibold">{profile?.full_name ?? "Signed in"}</p>
              <p className="text-xs capitalize text-slate-500">{profile?.role ?? "—"}</p>
            </div>
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-900 text-xs font-bold text-white">
              {initials(profile?.full_name ?? "User")}
            </span>
            <button
              type="button"
              onClick={async () => {
                await signOut();
                router.replace("/login");
              }}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
            >
              <LogOut className="h-4 w-4" aria-hidden="true" />
              <span className="hidden sm:inline">Sign out</span>
            </button>
          </div>
        </div>
      </header>

      <nav className="border-b border-slate-200 bg-white" aria-label="Main navigation">
        <div className="mx-auto flex max-w-7xl gap-1 overflow-x-auto px-4 sm:px-6">
          {items.map((item) => {
            const active = pathname === item.href || (item.href !== "/donors" && pathname.startsWith(`${item.href}/`));
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`whitespace-nowrap border-b-2 px-3 py-3 text-sm font-medium transition ${
                  active
                    ? "border-rose-600 text-rose-700"
                    : "border-transparent text-slate-600 hover:border-slate-300 hover:text-slate-900"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </div>
      </nav>

      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
        <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{title}</h1>
            {description ? <p className="mt-1 max-w-2xl text-sm text-slate-600">{description}</p> : null}
          </div>
          {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
        </div>
        {children}
      </main>

      <footer className="border-t border-slate-200 py-6 text-center text-xs text-slate-400">
        Eligibility is enforced by the API using the 90-day registry rule. Clinical screening is still required.
      </footer>
    </div>
  );
}
