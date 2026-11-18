"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/AuthProvider";
import { AppShell } from "@/components/AppShell";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { initials } from "@/lib/format";
import { dashboardPath } from "@/lib/navigation";

function ProfileContent() {
  const { profile, signOut } = useAuth();
  const router = useRouter();

  if (!profile) return null;

  return (
    <AppShell title="Profile" description="Your signed-in identity and effective permissions.">
      <div className="grid gap-6 lg:grid-cols-3">
        <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm lg:col-span-2">
          <div className="flex items-center gap-4">
            <span className="flex h-14 w-14 items-center justify-center rounded-full bg-rose-100 text-lg font-bold text-rose-700">
              {initials(profile.full_name)}
            </span>
            <div>
              <h2 className="text-xl font-bold">{profile.full_name}</h2>
              <p className="text-sm capitalize text-slate-500">{profile.role} account</p>
            </div>
          </div>

          <dl className="mt-6 divide-y divide-slate-100 border-t border-slate-100">
            <div className="flex flex-wrap justify-between gap-2 py-3 text-sm">
              <dt className="text-slate-500">Profile ID</dt>
              <dd className="font-mono text-xs text-slate-700">{profile.id}</dd>
            </div>
            <div className="flex flex-wrap justify-between gap-2 py-3 text-sm">
              <dt className="text-slate-500">Role</dt>
              <dd className="font-semibold capitalize">{profile.role}</dd>
            </div>
            <div className="flex flex-wrap justify-between gap-2 py-3 text-sm">
              <dt className="text-slate-500">Hospital ID</dt>
              <dd className="font-mono text-xs text-slate-700">
                {profile.hospital_id ?? "Not applicable"}
              </dd>
            </div>
          </dl>

          <div className="mt-6 flex flex-wrap gap-2">
            <Link
              href={dashboardPath(profile.role)}
              className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-700"
            >
              Go to dashboard
            </Link>
            <button
              type="button"
              onClick={async () => {
                await signOut();
                router.replace("/login");
              }}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
            >
              Sign out
            </button>
          </div>
        </section>

        <aside className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
            How permissions work
          </h2>
          <ul className="mt-4 space-y-3 text-sm leading-relaxed text-slate-600">
            <li>• The browser never sends a role claim to decide access.</li>
            <li>• Django verifies the JWT signature, expiry, issuer and audience.</li>
            <li>• The role is read from <code className="rounded bg-slate-100 px-1">public.profiles</code> using the token’s <code className="rounded bg-slate-100 px-1">sub</code>.</li>
            <li>• Hospital accounts are scoped to their own hospital’s requests.</li>
          </ul>
        </aside>
      </div>
    </AppShell>
  );
}

export default function ProfilePage() {
  return (
    <ProtectedRoute>
      <ProfileContent />
    </ProtectedRoute>
  );
}
