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

const draftAgent = {
  id: "agent-draft",
  display_name: "Draft Explorer",
  slug: "draft-explorer",
  current_version: { id: "version-draft", number: 1, state: "DRAFT", knowledge_status: "NOT_ADDED" },
  published_version: null,
  allowed_actions: ["EDIT_DRAFT"],
  next_action: "Continue defining the agent",
};

const reviewAgent = {
  id: "agent-review",
  display_name: "Review Explorer",
  slug: "review-explorer",
  current_version: { id: "version-review", number: 1, state: "IN_REVIEW", knowledge_status: "READY" },
  published_version: null,
  allowed_actions: [],
  next_action: "Waiting for teacher evaluation",
};

const publishedAgent = {
  id: "agent-live",
  display_name: "Live Explorer",
  slug: "live-explorer",
  current_version: { id: "version-draft-2", number: 2, state: "DRAFT", knowledge_status: "READY" },
  published_version: { id: "version-live", number: 1, state: "PUBLISHED", knowledge_status: "READY" },
  allowed_actions: ["EDIT_DRAFT"],
  next_action: "Continue defining the agent",
};

afterEach(() => {
  vi.clearAllMocks();
});

describe("StudioDashboard", () => {
  it("keeps a connection error inside the main landmark", async () => {
    studioMocks.restore.mockRejectedValue(new Error("Studio unavailable"));
    render(<StudioDashboard />);

    const heading = await screen.findByRole("heading", { name: "The workshop did not open." });
    const main = heading.closest("main");
    expect(main).toHaveAttribute("aria-live", "assertive");
    expect(main).not.toHaveAttribute("role", "alert");
  });

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

  it("shows only review-flow Agents in the active Reviews destination", async () => {
    studioMocks.restore.mockResolvedValue(studentSession);
    studioMocks.listAgents.mockResolvedValue({ agents: [draftAgent, reviewAgent, publishedAgent] });
    render(<StudioDashboard view="reviews" />);

    expect(await screen.findByRole("heading", { name: "Ready for a decision" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Reviews" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByText("Review Explorer")).toBeInTheDocument();
    expect(screen.queryByText("Draft Explorer")).not.toBeInTheDocument();
    expect(screen.queryByText("Live Explorer")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open review →" })).toHaveAttribute("href", "/studio/review/agent-review");
  });

  it("keeps a published version visible while a newer Draft exists", async () => {
    studioMocks.restore.mockResolvedValue(studentSession);
    studioMocks.listAgents.mockResolvedValue({ agents: [draftAgent, publishedAgent] });
    render(<StudioDashboard view="published" />);

    expect(await screen.findByRole("heading", { name: "Published agents" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Published" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByText("Live Explorer")).toBeInTheDocument();
    expect(screen.getByText("PUBLISHED")).toBeInTheDocument();
    expect(screen.queryByText("Draft Explorer")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open public Agent ↗" })).toHaveAttribute("href", "/p/live-explorer");
    expect(screen.getByRole("link", { name: "Manage release →" })).toHaveAttribute("href", "/studio/review/agent-live");
  });
});
