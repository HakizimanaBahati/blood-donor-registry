import { badgeClasses, badgeLabel } from "@/lib/format";
import type { EligibilityBadgeValue } from "@/lib/constants";

export function EligibilityBadge({
  badge,
  compact = false,
}: {
  badge: EligibilityBadgeValue;
  compact?: boolean;
}) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${badgeClasses(badge)}`}
      title="Computed by the server using the 90-day registry rule"
    >
      {badgeLabel(badge)}
      {compact ? null : <span className="sr-only"> (server-verified)</span>}
    </span>
  );
}
