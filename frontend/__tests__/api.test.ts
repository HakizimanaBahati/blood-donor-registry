import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiRequest, apiUrl, ApiError, isIneligibleDonorError } from "@/lib/api";

describe("API client", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("builds a base URL without duplicate slashes", () => {
    expect(apiUrl("/api/donors/")).toBe("http://127.0.0.1:8000/api/donors/");
    expect(apiUrl("api/health")).toBe("http://127.0.0.1:8000/api/health");
  });

  it("sends the bearer token and JSON body", async () => {
    const fetchMock = vi.fn(async (url: string, options: RequestInit) => {
      void url;
      void options;
      return {
        ok: true,
        status: 200,
        text: async () => JSON.stringify({ id: "created" }),
      };
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await apiRequest<{ id: string }>("/api/requests/", {
      method: "POST",
      token: "signed-jwt",
      body: { units: 2 },
    });

    expect(result).toEqual({ id: "created" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, options] = fetchMock.mock.calls[0]!;
    expect(url).toBe(apiUrl("/api/requests/"));
    expect((options.headers as Record<string, string>).Authorization).toBe("Bearer signed-jwt");
    expect(options.body).toBe('{"units":2}');
  });

  it("surfaces the server's ineligible-donor message and code", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 400,
        text: async () =>
          JSON.stringify({
            error: {
              code: "ineligible_donor",
              message: "This donor is not eligible to donate yet.",
              details: { message: "Please wait 80 more days.", days_until_eligible: 80 },
            },
          }),
      })),
    );

    try {
      await apiRequest("/api/requests/", { method: "POST" });
      throw new Error("Expected apiRequest to reject");
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      expect(isIneligibleDonorError(error)).toBe(true);
      expect((error as ApiError).status).toBe(400);
      expect((error as ApiError).message).toBe("Please wait 80 more days.");
      expect((error as ApiError).code).toBe("ineligible_donor");
    }
  });
});
