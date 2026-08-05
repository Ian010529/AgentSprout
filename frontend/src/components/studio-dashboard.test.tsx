import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { StudioDashboard } from "./studio-dashboard";

const navigation = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));
const studioMocks = vi.hoisted(() => ({
  restore: vi.fn(),
  listAgents: vi.fn(),
  changeRole: vi.fn(),
  signOut: vi.fn(),
  createAgent: vi.fn(),
  getAgent: vi.fn(),
  getVersion: vi.fn(),
  updateVersion: vi.fn(),
}));

vi.mock("next/navigation", () => ({ useRouter: () => navigation }));
vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, studioApi: studioMocks };
});

const studentSession = {
  session: { role: "STUDENT", expires_at: "2026-08-06T12:00:00Z" },
  csrf_token: "csrf-student",
};

afterEach(() => {
  vi.clearAllMocks();
});

describe("StudioDashboard", () => {
  it("restores a Student session and shows the real empty state", async () => {
    studioMocks.restore.mockResolvedValue(studentSession);
    studioMocks.listAgents.mockResolvedValue({ agents: [] });
    render(<StudioDashboard />);

    expect(screen.getByText("Restoring the workshop…")).toBeInTheDocument();
    expect(await screen.findByText("Build one useful thing.")).toBeInTheDocument();
    expect(screen.getByText("The workbench is clear.")).toBeInTheDocument();
  });

  it("shows the Teacher review shell without a creation action", async () => {
    studioMocks.restore.mockResolvedValue({
      session: { role: "TEACHER", expires_at: "2026-08-06T12:00:00Z" },
      csrf_token: "csrf-teacher",
    });
    studioMocks.listAgents.mockResolvedValue({ agents: [] });
    render(<StudioDashboard />);

    expect(await screen.findByText("Review what is ready.")).toBeInTheDocument();
    expect(screen.getByText("Nothing is waiting for review.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Create agent" })).not.toBeInTheDocument();
  });

  it("disables duplicate creation while one request is pending", async () => {
    studioMocks.restore.mockResolvedValue(studentSession);
    studioMocks.listAgents.mockResolvedValue({ agents: [] });
    studioMocks.createAgent.mockReturnValue(new Promise(() => undefined));
    render(<StudioDashboard />);
    await screen.findByText("Build one useful thing.");

    fireEvent.click(screen.getByRole("button", { name: "Create agent" }));
    const submit = screen.getByRole("button", { name: "Create Ocean Explorer" });
    fireEvent.click(submit);
    fireEvent.click(submit);

    await waitFor(() => expect(studioMocks.createAgent).toHaveBeenCalledTimes(1));
    expect(screen.getByRole("button", { name: "Creating once…" })).toBeDisabled();
  });
});
