import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EligibilityBadge } from "@/components/EligibilityBadge";

describe("EligibilityBadge", () => {
  it("renders server-provided eligibility states without recalculating them", () => {
    render(<EligibilityBadge badge="ineligible" />);
    expect(screen.getByText(/Not eligible yet/)).toBeInTheDocument();
  });

  it("renders the new-donor state", () => {
    render(<EligibilityBadge badge="no_history" compact />);
    expect(screen.getByText("New donor")).toBeInTheDocument();
  });
});
