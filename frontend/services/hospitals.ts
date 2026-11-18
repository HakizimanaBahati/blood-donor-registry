import { apiRequest } from "@/lib/api";
import type { Hospital, HospitalWritePayload, Paginated } from "@/types";

export function listHospitals(signal?: AbortSignal): Promise<Paginated<Hospital>> {
  return apiRequest<Paginated<Hospital>>("/api/hospitals/?page_size=100", { signal });
}

export function getHospital(id: string, signal?: AbortSignal): Promise<Hospital> {
  return apiRequest<Hospital>(`/api/hospitals/${encodeURIComponent(id)}/`, { signal });
}

export function createHospital(payload: HospitalWritePayload): Promise<Hospital> {
  return apiRequest<Hospital>("/api/hospitals/", { method: "POST", body: payload });
}
