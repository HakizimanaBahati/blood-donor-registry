import { formatDate, statusClasses } from "@/lib/format";
import type { BloodRequest } from "@/types";

export function RequestTable({ requests }: { requests: BloodRequest[] }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-3">Blood type</th>
            <th className="px-4 py-3">Units</th>
            <th className="px-4 py-3">Hospital</th>
            <th className="px-4 py-3">Donor</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Created</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {requests.map((request) => (
            <tr key={request.id} className="hover:bg-slate-50/70">
              <td className="px-4 py-3 font-semibold text-rose-700">{request.blood_type}</td>
              <td className="px-4 py-3 text-slate-700">{request.units}</td>
              <td className="px-4 py-3 text-slate-700">{request.hospital_name}</td>
              <td className="px-4 py-3 text-slate-600">
                {request.donor_name ? (
                  <span>
                    {request.donor_name}
                    <span className="ml-1 text-xs text-slate-400">({request.donor_blood_type})</span>
                  </span>
                ) : (
                  <span className="text-xs italic text-slate-400">Unassigned</span>
                )}
              </td>
              <td className="px-4 py-3">
                <span
                  className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold capitalize ring-1 ring-inset ${statusClasses(request.status)}`}
                >
                  {request.status}
                </span>
              </td>
              <td className="px-4 py-3 text-slate-500">{formatDate(request.created_at, true)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
