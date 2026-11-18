import Link from "next/link";

import { EligibilityBadge } from "@/components/EligibilityBadge";
import { formatDate } from "@/lib/format";
import type { Donor } from "@/types";

export function DonorTable({ donors }: { donors: Donor[] }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-3">Donor</th>
            <th className="px-4 py-3">Blood type</th>
            <th className="px-4 py-3">Last donation</th>
            <th className="px-4 py-3">Eligibility</th>
            <th className="px-4 py-3">Phone</th>
            <th className="px-4 py-3 text-right">Details</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {donors.map((donor) => (
            <tr key={donor.id} className="transition hover:bg-slate-50/70">
              <td className="px-4 py-3 font-medium text-slate-900">{donor.name}</td>
              <td className="px-4 py-3">
                <span className="rounded-md bg-rose-50 px-2 py-1 font-semibold text-rose-700">
                  {donor.blood_type}
                </span>
              </td>
              <td className="px-4 py-3 text-slate-600">{formatDate(donor.last_donation)}</td>
              <td className="px-4 py-3">
                <div className="flex flex-col items-start gap-1">
                  <EligibilityBadge badge={donor.eligibility_badge} compact />
                  <span className="text-xs text-slate-500">{donor.eligibility_message}</span>
                </div>
              </td>
              <td className="px-4 py-3 text-slate-600">
                {donor.phone ?? <span className="text-xs italic text-slate-400">Eligible donors only</span>}
              </td>
              <td className="px-4 py-3 text-right">
                <Link
                  href={`/donors/${donor.id}`}
                  className="text-sm font-semibold text-rose-600 hover:text-rose-800 hover:underline"
                >
                  View →
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
