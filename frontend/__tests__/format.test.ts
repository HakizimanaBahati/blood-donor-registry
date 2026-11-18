import { describe, expect, it } from "vitest";

import { badgeClasses, badgeLabel, formatDate, pluralize, todayInputValue } from "@/lib/format";

describe("presentation helpers", () => {
  it("labels the server-generated eligibility badges", () => {
    expect(badgeLabel("eligible")).toBe("Eligible");
    expect(badgeLabel("ineligible")).toBe("Not eligible yet");
    expect(badgeLabel("no_history")).toBe("New donor");
    expect(badgeClasses("ineligible")).toContain("text-rose-800");
  });

  it("formats missing and valid dates safely", () => {
    expect(formatDate(null)).toBe("—");
    expect(formatDate("2026-01-05")).toContain("2026");
  });

  it("pluralizes day counts for eligibility feedback", () => {
    expect(pluralize(1, "day")).toBe("1 day");
    expect(pluralize(80, "day")).toBe("80 days");
  });

  it("produces an ISO date for the date input maximum", () => {
    expect(todayInputValue()).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});
