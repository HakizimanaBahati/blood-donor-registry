import { describe, expect, it } from "vitest";

import { donorQueryString } from "@/services/donors";

describe("donor query builder", () => {
  it("encodes blood types and converts boolean eligibility", () => {
    const query = donorQueryString({
      page: 2,
      pageSize: 5,
      bloodType: "O+",
      eligible: true,
      search: "Jordan Lee",
      ordering: "-eligibility",
    });
    const params = new URLSearchParams(query);

    expect(params.get("page")).toBe("2");
    expect(params.get("page_size")).toBe("5");
    expect(params.get("blood_type")).toBe("O+");
    expect(params.get("eligible")).toBe("true");
    expect(params.get("search")).toBe("Jordan Lee");
    expect(params.get("ordering")).toBe("-eligibility");
  });

  it("omits empty filters", () => {
    expect(donorQueryString()).toBe("");
    expect(donorQueryString({ eligible: false, search: "   " })).toBe("?eligible=false");
  });
});
