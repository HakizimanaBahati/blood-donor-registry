export const BLOOD_TYPES = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"] as const;

export type BloodType = (typeof BLOOD_TYPES)[number];

export const REQUEST_STATUSES = ["pending", "fulfilled", "cancelled"] as const;

export type RequestStatus = (typeof REQUEST_STATUSES)[number];

export const ELIGIBILITY_BADGES = ["eligible", "ineligible", "no_history"] as const;

export type EligibilityBadgeValue = (typeof ELIGIBILITY_BADGES)[number];

/** Session key for the development-only token issued by Django's dev-login view. */
export const DEV_TOKEN_KEY = "bdr_dev_token";
