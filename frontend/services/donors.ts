import { apiRequest } from "@/lib/api";
import type { Donor, DonorWritePayload, Paginated } from "@/types";

export interface DonorQuery {
  page?: number;
  pageSize?: number;
  bloodType?: string;
  eligible?: boolean | null;
  search?: string;
  ordering?: string;
}

export function donorQueryString(query: DonorQuery = {}): string {
  const params = new URLSearchParams();
  if (query.page) params.set("page", String(query.page));
  if (query.pageSize) params.set("page_size", String(query.pageSize));
  if (query.bloodType) params.set("blood_type", query.bloodType);
  if (query.eligible !== undefined && query.eligible !== null) {
    params.set("eligible", query.eligible ? "true" : "false");
  }
  if (query.search?.trim()) params.set("search", query.search.trim());
  if (query.ordering) params.set("ordering", query.ordering);
  const serialized = params.toString();
  return serialized ? `?${serialized}` : "";
}

export function listDonors(query: DonorQuery = {}, signal?: AbortSignal): Promise<Paginated<Donor>> {
  return apiRequest<Paginated<Donor>>(`/api/donors/${donorQueryString(query)}`, { signal });
}

export function getDonor(id: string, signal?: AbortSignal): Promise<Donor> {
  return apiRequest<Donor>(`/api/donors/${encodeURIComponent(id)}/`, { signal });
}

export function createDonor(payload: DonorWritePayload): Promise<Donor> {
  return apiRequest<Donor>("/api/donors/", { method: "POST", body: payload });
}

export function updateDonor(id: string, payload: Partial<DonorWritePayload>): Promise<Donor> {
  return apiRequest<Donor>(`/api/donors/${encodeURIComponent(id)}/`, {
    method: "PATCH",
    body: payload,
  });
}

export function deleteDonor(id: string): Promise<void> {
  return apiRequest<void>(`/api/donors/${encodeURIComponent(id)}/`, { method: "DELETE" });
}
