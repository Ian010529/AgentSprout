import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AgentWorkspace } from "./agent-workspace";

const navigation = vi.hoisted(() => ({ replace: vi.fn(), push: vi.fn() }));
const studioMocks = vi.hoisted(() => ({
  restore: vi.fn(),
  listAgents: vi.fn(),
  changeRole: vi.fn(),
  signOut: vi.fn(),
  createAgent: vi.fn(),
  getAgent: vi.fn(),
  getVersion: vi.fn(),
  updateVersion: vi.fn(),
  uploadKnowledge: vi.fn(),
  getIngestionJob: vi.fn(),
  retryIngestion: vi.fn(),
  deleteKnowledge: vi.fn(),
  getLatestConversation: vi.fn(),
}));

vi.mock("next/navigation", () => ({ useRouter: () => navigation }));
vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, studioApi: studioMocks };
});

const version = {
  id: "version-1",
  agent_id: "agent-1",
  version_number: 1,
  state: "DRAFT",
  project_name: "Ocean Explorer",
  problem_to_solve: "Help learners understand the ocean using trusted evidence.",
  intended_users: "Students learning ocean science",
  audience_age: "AGE_12_17",
  success_goal: "Answer ocean questions clearly with evidence from the source.",
  welcome_message: "What would you like to discover about the ocean?",
  tone: "CURIOUS",
  response_length: "BALANCED",
  custom_instructions: "",
  active_document_id: null,
  knowledge_status: "NOT_ADDED",
  knowledge: { active_document: null, latest_job: null },
  allowed_actions: ["EDIT_DRAFT"],
  created_at: "2026-08-06T10:00:00Z",
  updated_at: "2026-08-06T10:00:00Z",
};

afterEach(() => {
  vi.clearAllMocks();
  window.history.replaceState(null, "", "/");
});

describe("AgentWorkspace", () => {
  it("keeps the unavailable Draft message inside the main landmark", async () => {
    studioMocks.restore.mockResolvedValue({
      session: { role: "STUDENT", expires_at: "2026-08-06T12:00:00Z" },
      csrf_token: "csrf-student",
    });
    studioMocks.getAgent.mockResolvedValue({ current_draft_version_id: null });

    render(<AgentWorkspace agentId="published-agent" />);

    const heading = await screen.findByRole("heading", { name: "This Agent has no editable Draft." });
    const main = heading.closest("main");
    expect(main).toHaveAttribute("aria-live", "assertive");
    expect(main).not.toHaveAttribute("role", "alert");
  });

  it("PATCHes only the editable field allowlist and restores saved values", async () => {
    studioMocks.restore.mockResolvedValue({
      session: { role: "STUDENT", expires_at: "2026-08-06T12:00:00Z" },
      csrf_token: "csrf-student",
    });
    studioMocks.getAgent.mockResolvedValue({ current_draft_version_id: "version-1" });
    studioMocks.getVersion.mockResolvedValue(version);
    studioMocks.updateVersion.mockImplementation(
      async (_versionId: string, payload: Record<string, unknown>) => ({ ...version, ...payload }),
    );
    render(<AgentWorkspace agentId="agent-1" />);

    const projectName = (await screen.findByLabelText("Project name")) as HTMLInputElement;
    fireEvent.change(projectName, { target: { value: "Ocean Field Guide" } });
    fireEvent.click(screen.getByRole("button", { name: "Save Draft" }));

    await waitFor(() => expect(studioMocks.updateVersion).toHaveBeenCalledTimes(1));
    const payload = studioMocks.updateVersion.mock.calls[0][1] as Record<string, unknown>;
    expect(Object.keys(payload).sort()).toEqual(
      [
        "audience_age",
        "custom_instructions",
        "intended_users",
        "problem_to_solve",
        "project_name",
        "response_length",
        "success_goal",
        "tone",
        "welcome_message",
      ].sort(),
    );
    expect(payload).not.toHaveProperty("state");
    expect(projectName.value).toBe("Ocean Field Guide");
  });

  it("shows one URL-backed stage and redirects a locked stage to Knowledge", async () => {
    window.history.replaceState(null, "", "/studio/agents/agent-1#test");
    studioMocks.restore.mockResolvedValue({
      session: { role: "STUDENT", expires_at: "2026-08-06T12:00:00Z" },
      csrf_token: "csrf-student",
    });
    studioMocks.getAgent.mockResolvedValue({ current_draft_version_id: "version-1" });
    studioMocks.getVersion.mockResolvedValue(version);

    render(<AgentWorkspace agentId="agent-1" />);

    const knowledgeButton = await screen.findByRole("button", { name: /Knowledge/ });
    const defineButton = screen.getByRole("button", { name: /Define/ });
    const testButton = screen.getByRole("button", { name: /Test/ });
    const definePanel = document.getElementById("workspace-panel-define");
    const knowledgePanel = document.getElementById("workspace-panel-knowledge");

    await waitFor(() => expect(window.location.hash).toBe("#knowledge"));
    expect(knowledgeButton).toHaveAttribute("aria-current", "step");
    expect(testButton).toBeDisabled();
    expect(knowledgePanel).toBeVisible();
    expect(definePanel).not.toBeVisible();

    fireEvent.click(defineButton);
    expect(window.location.hash).toBe("#define");
    expect(definePanel).toBeVisible();
    expect(knowledgePanel).not.toBeVisible();
  });

  it("keeps the Ready Submit sheet outside locked-stage layout rules", async () => {
    window.history.replaceState(null, "", "/studio/agents/agent-1#submit");
    studioMocks.restore.mockResolvedValue({
      session: { role: "STUDENT", expires_at: "2026-08-06T12:00:00Z" },
      csrf_token: "csrf-student",
    });
    studioMocks.getAgent.mockResolvedValue({ current_draft_version_id: "version-1" });
    studioMocks.getVersion.mockResolvedValue({
      ...version,
      active_document_id: "document-1",
      knowledge_status: "READY",
      knowledge: {
        active_document: {
          id: "document-1",
          original_filename: "ocean-literacy.pdf",
          status: "READY",
          page_count: 13,
          chunk_count: 42,
          sha256: "abc123",
          embedding_model: "text-embedding-3-small",
          ready_at: "2026-08-06T10:05:00Z",
        },
        latest_job: null,
      },
    });
    studioMocks.getLatestConversation.mockResolvedValue(null);

    render(<AgentWorkspace agentId="agent-1" />);

    const submit = await screen.findByRole("button", { name: "Submit v1 for review" });
    expect(window.location.hash).toBe("#submit");
    expect(submit.closest(".submit-stage")).not.toBeNull();
    expect(submit.closest(".locked-stages")).toBeNull();
    expect(document.getElementById("workspace-panel-submit")).toBeVisible();
  });
});
