import { DEV_TOKEN_KEY } from "@/lib/constants";
import { getAccessToken } from "@/lib/supabase";

const configuredBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
export const API_BASE_URL = configuredBase.replace(/\/+$/, "");

export function apiUrl(path: string): string {
  return `${API_BASE_URL}/${path.replace(/^\/+/, "")}`;
}

export interface ApiErrorEnvelope {
  code?: string;
  message?: string;
  details?: unknown;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function stringifyDetails(details: unknown): string | null {
  if (typeof details === "string") return details;
  const record = asRecord(details);
  if (!record) return null;
  const specific = record.message ?? record.detail;
  if (typeof specific === "string") return specific;

  const parts: string[] = [];
  for (const [field, value] of Object.entries(record)) {
    if (Array.isArray(value)) {
      parts.push(`${field}: ${value.join(" ")}`);
    } else if (typeof value === "string") {
      parts.push(`${field}: ${value}`);
    }
  }
  return parts.length ? parts.join(" · ") : null;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;
  readonly details?: unknown;

  constructor(message: string, status: number, payload?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    const envelope = asRecord(asRecord(payload)?.error) as ApiErrorEnvelope | null;
    this.code = envelope?.code;
    this.details = envelope?.details;
  }
}

function errorMessage(payload: unknown, status: number): string {
  const envelope = asRecord(asRecord(payload)?.error) as ApiErrorEnvelope | null;
  if (envelope) {
    const detailed = stringifyDetails(envelope.details);
    if (detailed) return detailed;
    if (envelope.message) return envelope.message;
  }
  const root = asRecord(payload);
  if (typeof root?.detail === "string") return root.detail;
  const detailedRoot = stringifyDetails(root?.detail);
  if (detailedRoot) return detailedRoot;
  if (status === 401) return "Your session has expired. Please sign in again.";
  if (status === 403) return "You do not have permission to do that.";
  if (status === 404) return "The requested item was not found.";
  return `Request failed (${status || "network"}).`;
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  /** Explicit token (used right after login before context state updates). */
  token?: string | null;
  /** Call public endpoints such as dev-login without an Authorization header. */
  skipAuth?: boolean;
  signal?: AbortSignal;
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const token = options.skipAuth
    ? null
    : options.token !== undefined
      ? options.token
      : await getAccessToken();

  const headers: Record<string, string> = { Accept: "application/json" };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;

  let response: Response;
  try {
    response = await fetch(apiUrl(path), {
      method: options.method ?? "GET",
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: options.signal,
      cache: "no-store",
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError("Cannot reach the API. Check that the Django server is running.", 0);
  }

  const text = await response.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = { detail: text };
    }
  }

  if (!response.ok) {
    throw new ApiError(errorMessage(payload, response.status), response.status, payload);
  }
  return payload as T;
}

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

export function isIneligibleDonorError(error: unknown): boolean {
  return error instanceof ApiError && error.code === "ineligible_donor";
}

/** Exposed for tests and diagnostics; the actual key lives in sessionStorage. */
export const DEV_TOKEN_STORAGE_KEY = DEV_TOKEN_KEY;
