import type { EligibilityBadgeValue } from "@/lib/constants";

export type Role = "admin" | "hospital";

export interface Profile {
  id: string;
  full_name: string;
  role: Role;
  hospital_id: string | null;
}

export interface Donor {
  id: string;
  name: string;
  blood_type: string;
  phone: string | null;
  last_donation: string | null;
  eligible: boolean;
  has_donation_history: boolean;
  days_since_last_donation: number | null;
  days_until_eligible: number;
  eligibility_message: string;
  eligibility_badge: EligibilityBadgeValue;
  created_at: string;
  updated_at: string;
}

export interface Hospital {
  id: string;
  name: string;
  location: string | null;
  phone: string | null;
  created_at: string;
}

export interface BloodRequest {
  id: string;
  hospital_id: string;
  hospital_name: string;
  blood_type: string;
  units: number;
  status: string;
  notes: string | null;
  donor_id: string | null;
  donor_name: string | null;
  donor_blood_type: string | null;
  donor_eligible: boolean | null;
  requester_profile_id: string;
  created_at: string;
  updated_at: string;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface DashboardSummary {
  total_donors: number;
  eligible_donors: number;
  ineligible_donors: number;
  total_hospitals: number;
  total_requests: number;
  recent_requests: BloodRequest[];
}

export type DonorsByBloodType = Record<string, number>;

export interface DonorWritePayload {
  name: string;
  blood_type: string;
  phone: string;
  last_donation: string | null;
}

export interface BloodRequestWritePayload {
  blood_type: string;
  units: number;
  status?: string;
  notes?: string | null;
  donor_id?: string | null;
  hospital_id?: string;
}

export interface HospitalWritePayload {
  name: string;
  location?: string | null;
  phone?: string | null;
}
