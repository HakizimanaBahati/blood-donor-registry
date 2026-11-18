import type { EligibilityBadgeValue } from "@/lib/constants";

export function formatDate(value: string | null | undefined, withTime = false): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    ...(withTime ? { hour: "numeric", minute: "2-digit" } : {}),
  });
}

export function todayInputValue(): string {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60_000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

export function badgeLabel(badge: EligibilityBadgeValue): string {
  switch (badge) {
    case "eligible":
      return "Eligible";
    case "ineligible":
      return "Not eligible yet";
    case "no_history":
      return "New donor";
  }
}

/** Presentation-only classes. Eligibility itself is always server-generated. */
export function badgeClasses(badge: EligibilityBadgeValue): string {
  switch (badge) {
    case "eligible":
      return "bg-emerald-100 text-emerald-800 ring-emerald-200";
    case "ineligible":
      return "bg-rose-100 text-rose-800 ring-rose-200";
    case "no_history":
      return "bg-sky-100 text-sky-800 ring-sky-200";
  }
}

export function statusClasses(status: string): string {
  switch (status.toLowerCase()) {
    case "fulfilled":
      return "bg-emerald-100 text-emerald-800 ring-emerald-200";
    case "cancelled":
      return "bg-slate-200 text-slate-700 ring-slate-300";
    default:
      return "bg-amber-100 text-amber-800 ring-amber-200";
  }
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

export function pluralize(count: number, singular: string, plural = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : plural}`;
}
