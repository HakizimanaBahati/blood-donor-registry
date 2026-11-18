import { apiRequest } from "@/lib/api";
import type { DashboardSummary, DonorsByBloodType } from "@/types";

export function getDonorsPerBloodType(signal?: AbortSignal): Promise<DonorsByBloodType> {
  return apiRequest<DonorsByBloodType>("/api/analytics/donors-per-blood-type/", { signal });
}

export function getDashboardSummary(signal?: AbortSignal): Promise<DashboardSummary> {
  return apiRequest<DashboardSummary>("/api/analytics/summary/", { signal });
}
