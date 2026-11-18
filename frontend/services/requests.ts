import { apiRequest } from "@/lib/api";
import type { BloodRequest, BloodRequestWritePayload, Paginated } from "@/types";

export interface RequestQuery {
  page?: number;
  pageSize?: number;
}

export function listRequests(query: RequestQuery = {}, signal?: AbortSignal): Promise<Paginated<BloodRequest>> {
  const params = new URLSearchParams();
  if (query.page) params.set("page", String(query.page));
  if (query.pageSize) params.set("page_size", String(query.pageSize));
  const serialized = params.toString();
  return apiRequest<Paginated<BloodRequest>>(`/api/requests/${serialized ? `?${serialized}` : ""}`, {
    signal,
  });
}

export function createRequest(payload: BloodRequestWritePayload): Promise<BloodRequest> {
  return apiRequest<BloodRequest>("/api/requests/", { method: "POST", body: payload });
}

export function updateRequestStatus(id: string, status: string): Promise<BloodRequest> {
  return apiRequest<BloodRequest>(`/api/requests/${encodeURIComponent(id)}/`, {
    method: "PATCH",
    body: { status },
  });
}
