import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AgentWorkspace } from "./agent-workspace";

const navigation = vi.hoisted(() => ({ replace: vi.fn() }));
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
  allowed_actions: ["EDIT_DRAFT"],
  created_at: "2026-08-06T10:00:00Z",
  updated_at: "2026-08-06T10:00:00Z",
};

afterEach(() => vi.clearAllMocks());

describe("AgentWorkspace", () => {
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
});
