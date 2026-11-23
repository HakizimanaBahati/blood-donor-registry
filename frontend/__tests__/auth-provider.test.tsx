import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider, useAuth } from "@/components/AuthProvider";
import type { Profile } from "@/types";

type MockSession = { access_token?: string; refresh_token?: string } | null;
type AuthStateCallback = (event: string, session: MockSession) => void;

const mocks = vi.hoisted(() => {
  return {
    getAccessToken: vi.fn(),
    setDevToken: vi.fn(),
    clearDevToken: vi.fn(),
    fetchProfile: vi.fn(),
    requestLogout: vi.fn(),
    devLogin: vi.fn(),
    signInWithPassword: vi.fn(),
    signOut: vi.fn(),
    onAuthStateChange: vi.fn(),
    unsubscribe: vi.fn(),
    authStateCallback: null as null | AuthStateCallback,
  };
});

vi.mock("@/lib/supabase", () => ({
  getAccessToken: mocks.getAccessToken,
  setDevToken: mocks.setDevToken,
  clearDevToken: mocks.clearDevToken,
  supabase: {
    auth: {
      signInWithPassword: mocks.signInWithPassword,
      signOut: mocks.signOut,
      onAuthStateChange: mocks.onAuthStateChange,
    },
  },
}));

vi.mock("@/services/auth", () => ({
  fetchProfile: mocks.fetchProfile,
  requestLogout: mocks.requestLogout,
  devLogin: mocks.devLogin,
}));

function Probe() {
  const { profile, status, error, signInWithPassword, signOut, refresh } = useAuth();
  return (
    <div>
      <div data-testid="status">{status}</div>
      <div data-testid="profile">{profile?.full_name ?? ""}</div>
      <div data-testid="error">{error ?? ""}</div>
      <button onClick={() => void signInWithPassword("admin@example.com", "password")}>login</button>
      <button onClick={() => void signOut()}>logout</button>
      <button onClick={() => void refresh()}>refresh</button>
    </div>
  );
}

describe("AuthProvider", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.authStateCallback = null;
    mocks.onAuthStateChange.mockImplementation((cb: AuthStateCallback) => {
      mocks.authStateCallback = cb;
      return { data: { subscription: { unsubscribe: mocks.unsubscribe } } };
    });
    mocks.requestLogout.mockResolvedValue({ message: "ok" });
    mocks.signOut.mockResolvedValue({ error: null });
  });

  it("successful Supabase login passes the returned access_token to /api/auth/me/", async () => {
    mocks.getAccessToken.mockResolvedValue(null);
    mocks.signInWithPassword.mockResolvedValue({
      data: { session: { access_token: "returned-access-token", refresh_token: "returned-refresh-token" } },
      error: null,
    });
    mocks.fetchProfile.mockResolvedValue({ id: "1", full_name: "Admin", role: "admin", hospital_id: null });

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("unauthenticated"));
    await act(async () => {
      screen.getByText("login").click();
    });

    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("authenticated"));
    expect(mocks.fetchProfile).toHaveBeenCalledWith("returned-access-token");
    expect(mocks.fetchProfile.mock.calls.every((c) => c[0] !== "returned-refresh-token")).toBe(true);
    expect(mocks.signOut).not.toHaveBeenCalled();
  });

  it("failed password login clears a persisted session without another /api/auth/me/ call", async () => {
    const previousProfile: Profile = {
      id: "1",
      full_name: "Admin",
      role: "admin",
      hospital_id: null,
    };
    mocks.getAccessToken.mockResolvedValue("previous-token");
    mocks.fetchProfile.mockResolvedValue(previousProfile);
    mocks.signInWithPassword.mockResolvedValue({
      data: { user: null, session: null },
      error: { message: "Invalid login credentials" },
    });
    mocks.signOut.mockImplementation(async () => {
      mocks.authStateCallback?.("SIGNED_OUT", null);
      return { error: null };
    });

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("authenticated"));
    await waitFor(() => expect(screen.getByTestId("profile").textContent).toBe("Admin"));

    const profileCallsBeforeFailure = mocks.fetchProfile.mock.calls.length;

    await act(async () => {
      screen.getByText("login").click();
    });

    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("unauthenticated"));
    expect(screen.getByTestId("profile").textContent).toBe("");
    expect(screen.getByTestId("error").textContent).toBe("Invalid login credentials");
    expect(mocks.signOut).toHaveBeenCalledWith({ scope: "local" });
    expect(mocks.clearDevToken).toHaveBeenCalled();
    expect(mocks.fetchProfile).toHaveBeenCalledTimes(profileCallsBeforeFailure);
  });

  it("failed password login invalidates an in-flight profile refresh", async () => {
    const previousProfile: Profile = {
      id: "1",
      full_name: "Admin",
      role: "admin",
      hospital_id: null,
    };
    let resolveInitialProfile: ((profile: Profile) => void) | undefined;
    mocks.getAccessToken.mockResolvedValue("previous-token");
    mocks.fetchProfile.mockImplementationOnce(
      () =>
        new Promise<Profile>((resolve) => {
          resolveInitialProfile = resolve;
        }),
    );
    mocks.signInWithPassword.mockResolvedValue({
      data: { user: null, session: null },
      error: { message: "Invalid login credentials" },
    });

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() => expect(mocks.fetchProfile).toHaveBeenCalledTimes(1));
    expect(screen.getByTestId("status").textContent).toBe("loading");

    await act(async () => {
      screen.getByText("login").click();
    });

    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("unauthenticated"));
    expect(mocks.signOut).toHaveBeenCalledWith({ scope: "local" });
    const profileCallsAfterFailure = mocks.fetchProfile.mock.calls.length;

    await act(async () => {
      resolveInitialProfile?.(previousProfile);
    });

    expect(screen.getByTestId("status").textContent).toBe("unauthenticated");
    expect(screen.getByTestId("profile").textContent).toBe("");
    expect(mocks.fetchProfile).toHaveBeenCalledTimes(profileCallsAfterFailure);
  });

  it("failed password login preserves the original error when local sign-out fails", async () => {
    const previousProfile: Profile = {
      id: "1",
      full_name: "Admin",
      role: "admin",
      hospital_id: null,
    };
    mocks.getAccessToken.mockResolvedValue("previous-token");
    mocks.fetchProfile.mockResolvedValue(previousProfile);
    mocks.signInWithPassword.mockResolvedValue({
      data: { user: null, session: null },
      error: { message: "Invalid login credentials" },
    });
    mocks.signOut.mockRejectedValue(new Error("network unavailable"));

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("authenticated"));
    const profileCallsBeforeFailure = mocks.fetchProfile.mock.calls.length;

    await act(async () => {
      screen.getByText("login").click();
    });

    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("unauthenticated"));
    expect(screen.getByTestId("profile").textContent).toBe("");
    expect(screen.getByTestId("error").textContent).toBe("Invalid login credentials");
    expect(mocks.signOut).toHaveBeenCalledWith({ scope: "local" });
    expect(mocks.fetchProfile).toHaveBeenCalledTimes(profileCallsBeforeFailure);
  });

  it("missing session does not send an authenticated request", async () => {
    mocks.getAccessToken.mockResolvedValue(null);

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("unauthenticated"));
    expect(mocks.fetchProfile).not.toHaveBeenCalled();
  });

  it("failed Supabase session retrieval is handled safely", async () => {
    mocks.getAccessToken.mockRejectedValue(new Error("storage failure"));

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("unauthenticated"));
    expect(mocks.fetchProfile).not.toHaveBeenCalled();
  });

  it("TOKEN_REFRESHED updates the profile using the latest access token", async () => {
    mocks.getAccessToken.mockResolvedValue(null);
    mocks.fetchProfile.mockResolvedValue({ id: "1", full_name: "Admin", role: "admin", hospital_id: null });

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("unauthenticated"));
    await act(async () => {
      mocks.authStateCallback?.("TOKEN_REFRESHED", { access_token: "fresh-token", refresh_token: "refresh-token" });
    });

    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("authenticated"));
    expect(mocks.fetchProfile).toHaveBeenCalledWith("fresh-token");
    expect(mocks.fetchProfile.mock.calls.every((c) => c[0] !== "refresh-token")).toBe(true);
  });

  it("concurrent refresh calls cannot overwrite newer authentication state", async () => {
    let resolveOld: ((v: Profile | null) => void) | undefined;
    let resolveNew: ((v: Profile | null) => void) | undefined;
    mocks.getAccessToken.mockResolvedValue("old-token");
    mocks.fetchProfile
      .mockImplementationOnce(() => new Promise((resolve) => { resolveOld = resolve; }))
      .mockImplementationOnce(() => new Promise((resolve) => { resolveNew = resolve; }));

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() => expect(mocks.fetchProfile).toHaveBeenCalledTimes(1));

    await act(async () => {
      screen.getByText("refresh").click();
    });
    await waitFor(() => expect(mocks.fetchProfile).toHaveBeenCalledTimes(2));

    await act(async () => {
      resolveNew?.({ id: "2", full_name: "New User", role: "admin", hospital_id: null });
    });
    await waitFor(() => expect(screen.getByTestId("profile").textContent).toBe("New User"));

    await act(async () => {
      resolveOld?.({ id: "1", full_name: "Old User", role: "hospital", hospital_id: "h1" });
    });
    await waitFor(() => expect(screen.getByTestId("profile").textContent).toBe("New User"));
    expect(screen.getByTestId("status").textContent).toBe("authenticated");
  });

  it("sign-out clears the authenticated profile", async () => {
    mocks.getAccessToken.mockResolvedValue("token");
    mocks.fetchProfile.mockResolvedValue({ id: "1", full_name: "Admin", role: "admin", hospital_id: null });

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("authenticated"));
    await act(async () => {
      screen.getByText("logout").click();
    });

    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("unauthenticated"));
    expect(screen.getByTestId("profile").textContent).toBe("");
    expect(mocks.clearDevToken).toHaveBeenCalled();
    expect(mocks.signOut).toHaveBeenCalledTimes(1);
    expect(mocks.signOut.mock.calls[0]).toEqual([]);
  });

  it("no refresh_token is sent to Django", async () => {
    mocks.getAccessToken.mockResolvedValue(null);
    mocks.signInWithPassword.mockResolvedValue({
      data: { session: { access_token: "access-only", refresh_token: "refresh-secret" } },
      error: null,
    });
    mocks.fetchProfile.mockResolvedValue({ id: "1", full_name: "Admin", role: "admin", hospital_id: null });

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("unauthenticated"));

    await act(async () => {
      screen.getByText("login").click();
    });
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("authenticated"));

    for (const call of mocks.fetchProfile.mock.calls) {
      expect(call[0]).not.toBe("refresh-secret");
      expect(String(call[0])).not.toContain("refresh-secret");
    }
  });
});
