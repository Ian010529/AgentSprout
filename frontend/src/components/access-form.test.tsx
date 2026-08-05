import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AccessForm } from "./access-form";

const navigation = vi.hoisted(() => ({
  replace: vi.fn(),
  searchParams: new URLSearchParams(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: navigation.replace }),
  useSearchParams: () => navigation.searchParams,
}));

afterEach(() => {
  navigation.replace.mockReset();
  navigation.searchParams = new URLSearchParams();
  vi.unstubAllGlobals();
});

describe("AccessForm", () => {
  it("shows a generic invalid-code error without retaining the code", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: {
              code: "ACCESS_DENIED",
              message: "The Studio access code is not valid.",
              request_id: "request-denied",
              retryable: false,
            },
          }),
          { status: 401, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    render(<AccessForm />);
    const input = screen.getByLabelText("Access code");
    fireEvent.change(input, { target: { value: "wrong-code" } });
    fireEvent.submit(input.closest("form")!);

    expect(await screen.findByRole("alert")).toHaveTextContent("not recognized");
    expect(navigation.replace).not.toHaveBeenCalled();
  });

  it("renders the server retry window for rate limits", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: {
              code: "ACCESS_RATE_LIMITED",
              message: "Too many access attempts.",
              retry_after_seconds: 45,
            },
          }),
          { status: 429, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    render(<AccessForm />);
    fireEvent.change(screen.getByLabelText("Access code"), { target: { value: "wrong-code" } });
    fireEvent.click(screen.getByRole("button", { name: "Enter Studio" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("45 seconds");
  });

  it("clears the code and replaces the route after successful access", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            session: { role: "STUDENT", expires_at: "2026-08-06T12:00:00Z" },
            csrf_token: "csrf-token",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    render(<AccessForm />);
    const input = screen.getByLabelText("Access code") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "accepted-code" } });
    fireEvent.click(screen.getByRole("button", { name: "Enter Studio" }));

    await waitFor(() => expect(navigation.replace).toHaveBeenCalledWith("/studio"));
    expect(input.value).toBe("");
  });
});
