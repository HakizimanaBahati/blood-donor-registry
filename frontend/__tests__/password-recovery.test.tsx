import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

type MockSession = { access_token?: string } | null;
type AuthStateCallback = (event: string, session: MockSession) => void;

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn(),
  searchParams: new URLSearchParams(),
  getAccessToken: vi.fn(),
  setDevToken: vi.fn(),
  clearDevToken: vi.fn(),
  fetchProfile: vi.fn(),
  requestLogout: vi.fn(),
  devLogin: vi.fn(),
  signInWithPassword: vi.fn(),
  signOut: vi.fn(),
  resetPasswordForEmail: vi.fn(),
  exchangeCodeForSession: vi.fn(),
  getSession: vi.fn(),
  updateUser: vi.fn(),
  onAuthStateChange: vi.fn(),
  unsubscribe: vi.fn(),
  authStateCallback: null as null | AuthStateCallback,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push, replace: mocks.replace }),
  useSearchParams: () => mocks.searchParams,
  usePathname: () => "/login",
}));

vi.mock("@/lib/supabase", () => ({
  getAccessToken: mocks.getAccessToken,
  setDevToken: mocks.setDevToken,
  clearDevToken: mocks.clearDevToken,
  isDevLoginEnabled: () => false,
  supabase: {
    auth: {
      signInWithPassword: mocks.signInWithPassword,
      signOut: mocks.signOut,
      resetPasswordForEmail: mocks.resetPasswordForEmail,
      exchangeCodeForSession: mocks.exchangeCodeForSession,
      getSession: mocks.getSession,
      updateUser: mocks.updateUser,
      onAuthStateChange: mocks.onAuthStateChange,
    },
  },
}));

vi.mock("@/services/auth", () => ({
  fetchProfile: mocks.fetchProfile,
  requestLogout: mocks.requestLogout,
  devLogin: mocks.devLogin,
}));

import { AuthProvider, useAuth } from "@/components/AuthProvider";
import LoginPage from "@/app/login/page";
import AuthCallbackPage from "@/app/auth/callback/page";
import ResetPasswordPage from "@/app/auth/reset-password/page";

function AuthProbe() {
  const { status, profile, completeRecovery, markRecovery } = useAuth();
  return (
    <div>
      <div data-testid="status">{status}</div>
      <div data-testid="profile">{profile?.full_name ?? ""}</div>
      <button onClick={() => markRecovery()}>mark-recovery</button>
      <button onClick={() => void completeRecovery()}>complete-recovery</button>
    </div>
  );
}

describe("password recovery flow", () => {
  let consoleErrorSpy: ReturnType<typeof vi.spyOn>;
  let consoleWarnSpy: ReturnType<typeof vi.spyOn>;
  let consoleLogSpy: ReturnType<typeof vi.spyOn>;
  let consoleInfoSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.clearAllMocks();
    mocks.searchParams = new URLSearchParams();
    mocks.authStateCallback = null;
    mocks.onAuthStateChange.mockImplementation((cb: AuthStateCallback) => {
      mocks.authStateCallback = cb;
      return { data: { subscription: { unsubscribe: mocks.unsubscribe } } };
    });
    mocks.getAccessToken.mockResolvedValue(null);
    mocks.signOut.mockResolvedValue({ error: null });
    mocks.requestLogout.mockResolvedValue({ message: "ok" });
    mocks.getSession.mockResolvedValue({ data: { session: null }, error: null });
    consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    consoleWarnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    consoleLogSpy = vi.spyOn(console, "log").mockImplementation(() => {});
    consoleInfoSpy = vi.spyOn(console, "info").mockImplementation(() => {});
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
    consoleWarnSpy.mockRestore();
    consoleLogSpy.mockRestore();
    consoleInfoSpy.mockRestore();
  });

  function expectNoSensitiveLogs(sensitive: string[]) {
    const calls = [
      ...consoleErrorSpy.mock.calls,
      ...consoleWarnSpy.mock.calls,
      ...consoleLogSpy.mock.calls,
      ...consoleInfoSpy.mock.calls,
    ].flat().map(String);
    for (const value of sensitive) {
      for (const call of calls) {
        expect(call).not.toContain(value);
      }
    }
  }

  it("requests recovery email and shows generic success message", async () => {
    mocks.resetPasswordForEmail.mockResolvedValue({ data: {}, error: null });

    render(
      <AuthProvider>
        <LoginPage />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByText("Forgot password?")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Forgot password?"));
    fireEvent.change(screen.getByLabelText("Email for password reset"), {
      target: { value: "admin@example.com" },
    });
    await act(async () => {
      fireEvent.click(screen.getByText("Send password reset link"));
    });

    await waitFor(() =>
      expect(
        screen.getByText("If an account exists for that email address, a password reset link has been sent."),
      ).toBeInTheDocument(),
    );
    expect(mocks.resetPasswordForEmail).toHaveBeenCalledWith(
      "admin@example.com",
      expect.objectContaining({ redirectTo: expect.stringContaining("/auth/callback") }),
    );
    expectNoSensitiveLogs(["password123", "admin@example.com-password"]);
  });

  it("shows safe generic error when recovery email request fails", async () => {
    mocks.resetPasswordForEmail.mockResolvedValue({ data: null, error: { message: "rate limited" } });

    render(
      <AuthProvider>
        <LoginPage />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByText("Forgot password?")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Forgot password?"));
    fireEvent.change(screen.getByLabelText("Email for password reset"), {
      target: { value: "missing@example.com" },
    });
    await act(async () => {
      fireEvent.click(screen.getByText("Send password reset link"));
    });

    await waitFor(() =>
      expect(
        screen.getByText("Unable to send a password reset email right now. Please try again later."),
      ).toBeInTheDocument(),
    );
    expect(screen.queryByText(/rate limited/i)).not.toBeInTheDocument();
  });

  it("handles callback with valid authorization code", async () => {
    mocks.searchParams = new URLSearchParams("code=valid-code");
    mocks.exchangeCodeForSession.mockResolvedValue({ data: { session: { access_token: "a" } }, error: null });
    mocks.getSession.mockResolvedValue({ data: { session: { access_token: "a" } }, error: null });

    render(
      <AuthProvider>
        <AuthCallbackPage />
      </AuthProvider>,
    );

    await waitFor(() => expect(mocks.exchangeCodeForSession).toHaveBeenCalledWith("valid-code"));
    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith("/auth/reset-password"));
    expectNoSensitiveLogs(["valid-code", "a"]);
  });

  it("handles invalid/expired recovery links safely", async () => {
    mocks.searchParams = new URLSearchParams("error=access_denied&error_code=otp_expired&error_description=Email+link+is+invalid+or+has+expired");

    render(
      <AuthProvider>
        <AuthCallbackPage />
      </AuthProvider>,
    );

    await waitFor(() =>
      expect(
        screen.getByText("This password recovery link is invalid or has expired. Request a new password reset email."),
      ).toBeInTheDocument(),
    );
    expect(mocks.replace).not.toHaveBeenCalledWith("/auth/reset-password");
  });

  it("handles invalid recovery code when no session can be established", async () => {
    mocks.searchParams = new URLSearchParams("code=invalid-code");
    mocks.exchangeCodeForSession.mockResolvedValue({ data: { session: null }, error: { message: "invalid" } });
    mocks.getSession.mockResolvedValue({ data: { session: null }, error: null });

    render(
      <AuthProvider>
        <AuthCallbackPage />
      </AuthProvider>,
    );

    await waitFor(() => expect(mocks.exchangeCodeForSession).toHaveBeenCalledWith("invalid-code"));
    await waitFor(() =>
      expect(
        screen.getByText("This password recovery link is invalid or has expired. Request a new password reset email."),
      ).toBeInTheDocument(),
    );
    expect(mocks.replace).not.toHaveBeenCalledWith("/auth/reset-password");
  });

  it("handles PASSWORD_RECOVERY event by entering recovery state", async () => {
    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("unauthenticated"));
    await act(async () => {
      mocks.authStateCallback?.("PASSWORD_RECOVERY", { access_token: "recovery-token" });
    });

    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("recovery"));
    expect(screen.getByTestId("profile").textContent).toBe("");
  });

  it("updates password successfully and completes recovery", async () => {
    mocks.getSession.mockResolvedValue({ data: { session: { access_token: "recovery-token" } }, error: null });
    mocks.updateUser.mockResolvedValue({ data: { user: { id: "u1" } }, error: null });
    mocks.getAccessToken.mockResolvedValueOnce(null).mockResolvedValue("recovery-token");
    mocks.fetchProfile.mockResolvedValue({ id: "u1", full_name: "Admin", role: "admin", hospital_id: null });

    render(
      <AuthProvider>
        <AuthProbe />
        <ResetPasswordPage />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("unauthenticated"));
    await act(async () => {
      screen.getByText("mark-recovery").click();
    });
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("recovery"));

    fireEvent.change(screen.getByLabelText("New password"), { target: { value: "NewPassword123!" } });
    fireEvent.change(screen.getByLabelText("Confirm new password"), { target: { value: "NewPassword123!" } });
    await act(async () => {
      fireEvent.click(screen.getByText("Update password"));
    });

    await waitFor(() => expect(mocks.updateUser).toHaveBeenCalledWith({ password: "NewPassword123!" }));
    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith("/admin/dashboard"));
    expectNoSensitiveLogs(["NewPassword123!", "recovery-token"]);
  });

  it("shows safe error when password update fails", async () => {
    mocks.getSession.mockResolvedValue({ data: { session: { access_token: "recovery-token" } }, error: null });
    mocks.updateUser.mockResolvedValue({ data: null, error: { message: "weak password" } });

    render(
      <AuthProvider>
        <AuthProbe />
        <ResetPasswordPage />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("unauthenticated"));
    await act(async () => {
      screen.getByText("mark-recovery").click();
    });
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("recovery"));

    fireEvent.change(screen.getByLabelText("New password"), { target: { value: "NewPassword123!" } });
    fireEvent.change(screen.getByLabelText("Confirm new password"), { target: { value: "NewPassword123!" } });
    await act(async () => {
      fireEvent.click(screen.getByText("Update password"));
    });

    await waitFor(() =>
      expect(
        screen.getByText("Unable to update your password. Please request a new recovery link and try again."),
      ).toBeInTheDocument(),
    );
    expect(screen.queryByText(/weak password/i)).not.toBeInTheDocument();
  });

  it("rejects password confirmation mismatch without calling updateUser", async () => {
    mocks.getSession.mockResolvedValue({ data: { session: { access_token: "recovery-token" } }, error: null });

    render(
      <AuthProvider>
        <AuthProbe />
        <ResetPasswordPage />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("unauthenticated"));
    await act(async () => {
      screen.getByText("mark-recovery").click();
    });
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("recovery"));

    fireEvent.change(screen.getByLabelText("New password"), { target: { value: "NewPassword123!" } });
    fireEvent.change(screen.getByLabelText("Confirm new password"), { target: { value: "Different123!" } });
    await act(async () => {
      fireEvent.click(screen.getByText("Update password"));
    });

    await waitFor(() => expect(screen.getByText("Passwords do not match.")).toBeInTheDocument());
    expect(mocks.updateUser).not.toHaveBeenCalled();
  });
});
