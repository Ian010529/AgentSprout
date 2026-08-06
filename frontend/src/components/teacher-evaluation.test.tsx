import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TeacherEvaluation } from "./teacher-evaluation";

const navigation = vi.hoisted(() => ({ replace: vi.fn(), push: vi.fn() }));
const studioMocks = vi.hoisted(() => ({
  restore: vi.fn(),
  getAgent: vi.fn(),
  getVersion: vi.fn(),
  listEvaluations: vi.fn(),
  getEvaluationCases: vi.fn(),
  getEvaluationCase: vi.fn(),
  getEvaluation: vi.fn(),
  startEvaluation: vi.fn(),
  changeRole: vi.fn(),
  signOut: vi.fn(),
  requestChanges: vi.fn(),
  createNextVersion: vi.fn(),
  approveVersion: vi.fn(),
  compareVersions: vi.fn(),
}));

vi.mock("next/navigation", () => ({ useRouter: () => navigation }));
vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, studioApi: { ...original.studioApi, ...studioMocks } };
});

const version = {
  id: "version-1", agent_id: "agent-1", version_number: 1, state: "IN_REVIEW",
  project_name: "Ocean Explorer", problem_to_solve: "Help learners understand ocean science.",
  intended_users: "Students", audience_age: "AGE_12_17", success_goal: "Ground every answer.",
  welcome_message: "Explore the ocean.", tone: "CURIOUS", response_length: "BALANCED",
  custom_instructions: "", active_document_id: "doc-1", knowledge_status: "READY",
  knowledge: { active_document: null, latest_job: null }, allowed_actions: ["RUN_EVALUATION"],
  what_changed: null, why_changed: null, source_version_id: null, submitted_at: "2026-08-06T10:01:00Z", approved_at: null, reviews: [],
  created_at: "2026-08-06T10:00:00Z", updated_at: "2026-08-06T10:01:00Z",
};
const run = {
  id: "eval-1", version_id: "version-1", state: "COMPLETED",
  progress: { completed: 16, total: 16, passed: 15, failed: 1, errors: 0 },
  models: { online: "gpt-4o-mini-2024-07-18", judge: "gpt-4.1-mini-2025-04-14", embedding: "text-embedding-3-small", moderation: "omni-moderation-latest" },
  metrics: { grounded_pass_rate: 0.75, age_average: 4.5, instruction_average: 4.3 },
  usage: { input_tokens: 1200, output_tokens: 400, estimated_cost_usd: 0.0042 },
  release_eligible: false, safe_error: null, created_at: "2026-08-06T10:02:00Z", finished_at: "2026-08-06T10:03:00Z",
};
const evaluationCase = {
  id: "result-1", case_key: "KNW-01", category: "KNOWLEDGE", safe_prompt: "How do currents affect climate?",
  expected_result_type: "ANSWERED", actual_result_type: "ANSWERED", state: "COMPLETED", passed: true, blocking: false, safe_error_code: null,
};

afterEach(() => vi.clearAllMocks());

describe("TeacherEvaluation", () => {
  it("restores a completed run, filters cases, and opens reproducible evidence", async () => {
    studioMocks.restore.mockResolvedValue({ session: { role: "TEACHER", expires_at: "later" }, csrf_token: "csrf" });
    studioMocks.getAgent.mockResolvedValue({ versions: [{ id: "version-1" }] });
    studioMocks.getVersion.mockResolvedValue(version);
    studioMocks.listEvaluations.mockResolvedValue({ evaluations: [run] });
    studioMocks.getEvaluationCases.mockResolvedValue({ cases: [evaluationCase] });
    studioMocks.getEvaluationCase.mockResolvedValue({ ...evaluationCase, deterministic_checks: { expected_result_type: true }, evidence: [{ page_number: 9 }], judge: { evidence_score: 5, age_score: 5, instruction_score: 5, rationale: "Supported by page 9." }, usage: {}, latency_ms: 800, trace_run_id: "chat-1" });
    render(<TeacherEvaluation agentId="agent-1" />);

    const progress = await screen.findByText("cases persisted");
    expect(progress.parentElement).toHaveTextContent("16/16");
    expect(screen.getByText("gpt-4.1-mini-2025-04-14")).toBeInTheDocument();
    fireEvent.click(screen.getByText("KNW-01"));
    expect(await screen.findByRole("complementary", { name: "Evaluation case evidence" })).toHaveTextContent("Supported by page 9");
    expect(studioMocks.startEvaluation).not.toHaveBeenCalled();
  });

  it("starts one server-owned evaluation when no historical run exists", async () => {
    studioMocks.restore.mockResolvedValue({ session: { role: "TEACHER", expires_at: "later" }, csrf_token: "csrf" });
    studioMocks.getAgent.mockResolvedValue({ versions: [{ id: "version-1" }] });
    studioMocks.getVersion.mockResolvedValue(version);
    studioMocks.listEvaluations.mockResolvedValue({ evaluations: [] });
    studioMocks.startEvaluation.mockResolvedValue({ evaluation_run_id: "eval-2", state: "QUEUED", total_cases: 16 });
    studioMocks.getEvaluation.mockResolvedValue({ ...run, id: "eval-2", state: "QUEUED", progress: { completed: 0, total: 16, passed: 0, failed: 0, errors: 0 }, metrics: null });
    render(<TeacherEvaluation agentId="agent-1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Run 16-case evaluation" }));
    await waitFor(() => expect(studioMocks.startEvaluation).toHaveBeenCalledTimes(1));
  });

  it("persists required Teacher feedback for a completed run", async () => {
    studioMocks.restore.mockResolvedValue({ session: { role: "TEACHER", expires_at: "later" }, csrf_token: "csrf" });
    studioMocks.getAgent.mockResolvedValue({ versions: [{ id: "version-1" }] });
    studioMocks.getVersion.mockResolvedValue(version);
    studioMocks.listEvaluations.mockResolvedValue({ evaluations: [run] });
    studioMocks.getEvaluationCases.mockResolvedValue({ cases: [evaluationCase] });
    studioMocks.requestChanges.mockResolvedValue({ version: { ...version, state: "CHANGES_REQUESTED" }, review: {} });
    render(<TeacherEvaluation agentId="agent-1" />);
    fireEvent.change(await screen.findByLabelText("Required feedback"), { target: { value: "Use the expected evidence page." } });
    fireEvent.click(screen.getByRole("button", { name: "Request changes" }));
    await waitFor(() => expect(studioMocks.requestChanges).toHaveBeenCalledWith("version-1", "eval-1", "Use the expected evidence page.", "csrf"));
  });

  it("requires Student reflection before creating the next Draft", async () => {
    const changed = { ...version, state: "CHANGES_REQUESTED", reviews: [{ id: "review-1", evaluation_run_id: "eval-1", decision: "REQUEST_CHANGES", feedback: "Use the expected page.", created_at: "now" }] };
    studioMocks.restore.mockResolvedValue({ session: { role: "STUDENT", expires_at: "later" }, csrf_token: "csrf" });
    studioMocks.getAgent.mockResolvedValue({ versions: [{ id: "version-1" }] });
    studioMocks.getVersion.mockResolvedValue(changed);
    studioMocks.createNextVersion.mockResolvedValue({ ...changed, id: "version-2", version_number: 2, state: "DRAFT" });
    render(<TeacherEvaluation agentId="agent-1" />);
    fireEvent.change(await screen.findByLabelText("What changed"), { target: { value: "Used page 11 evidence." } });
    fireEvent.change(screen.getByLabelText("Why changed"), { target: { value: "Teacher feedback identified weak grounding." } });
    fireEvent.click(screen.getByRole("button", { name: "Create Draft v2" }));
    await waitFor(() => expect(studioMocks.createNextVersion).toHaveBeenCalled());
    expect(navigation.push).toHaveBeenCalledWith("/studio/agents/agent-1");
  });
});
