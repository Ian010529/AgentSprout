import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, type Conversation, type VersionDetail } from "@/lib/api";

import { PlaygroundPanel } from "./playground-panel";

const studioMocks = vi.hoisted(() => ({
  startRun: vi.fn(),
  getRun: vi.fn(),
  getConversation: vi.fn(),
  getLatestConversation: vi.fn(),
  getTrace: vi.fn(),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, studioApi: { ...original.studioApi, ...studioMocks } };
});

const version: VersionDetail = {
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
  active_document_id: "document-1",
  knowledge_status: "READY",
  knowledge: {
    active_document: {
      id: "document-1",
      original_filename: "ocean-literacy.pdf",
      status: "READY",
      page_count: 13,
      chunk_count: 48,
      sha256: "a".repeat(64),
      embedding_model: "text-embedding-3-small",
      ready_at: "2026-08-06T10:00:00Z",
    },
    latest_job: null,
  },
  what_changed: null,
  why_changed: null,
  source_version_id: null,
  submitted_at: null,
  approved_at: null,
  reviews: [],
  allowed_actions: ["EDIT_DRAFT"],
  created_at: "2026-08-06T10:00:00Z",
  updated_at: "2026-08-06T10:00:00Z",
};

const userConversation: Conversation = {
  id: "conversation-1",
  version_id: version.id,
  updated_at: "2026-08-06T10:01:00Z",
  messages: [
    {
      id: "message-user",
      run_id: "run-1",
      role: "USER",
      content: "How do currents affect climate?",
      result_type: null,
      citations: [],
      created_at: "2026-08-06T10:01:00Z",
    },
  ],
};

const answeredConversation: Conversation = {
  ...userConversation,
  updated_at: "2026-08-06T10:01:02Z",
  messages: [
    ...userConversation.messages,
    {
      id: "message-answer",
      run_id: "run-1",
      role: "ASSISTANT",
      content: "Ocean currents move heat and influence regional climate.",
      result_type: "ANSWERED",
      citations: [
        {
          chunk_id: "chunk-1",
          filename: "ocean-literacy.pdf",
          page_number: 9,
          excerpt: "The ocean transports heat and affects climate.",
        },
      ],
      created_at: "2026-08-06T10:01:02Z",
    },
  ],
};

afterEach(() => vi.clearAllMocks());

describe("PlaygroundPanel", () => {
  it("sends through assistant-ui and renders only the validated answer with citation", async () => {
    studioMocks.getLatestConversation.mockResolvedValue(null);
    studioMocks.startRun.mockResolvedValue({
      run_id: "run-1",
      conversation_id: "conversation-1",
      phase: "QUEUED",
      poll_after_ms: 500,
    });
    studioMocks.getConversation
      .mockResolvedValueOnce(userConversation)
      .mockResolvedValueOnce(answeredConversation);
    studioMocks.getRun.mockResolvedValue({
      id: "run-1",
      conversation_id: "conversation-1",
      phase: "COMPLETED",
      status: "COMPLETED",
      display_stage: "Answer ready",
      result: {
        type: "ANSWERED",
        answer: answeredConversation.messages[1].content,
        citations: answeredConversation.messages[1].citations,
      },
      safe_error: null,
      retryable: false,
    });
    render(
      <PlaygroundPanel role="STUDENT" csrf="csrf" version={version} onSessionExpired={vi.fn()} />,
    );

    const input = await screen.findByLabelText("Message Ocean Explorer");
    await waitFor(() => expect(input).toBeEnabled());
    fireEvent.change(input, { target: { value: "How do currents affect climate?" } });
    fireEvent.click(screen.getByRole("button", { name: /Send question/ }));

    await waitFor(() => expect(studioMocks.startRun).toHaveBeenCalledTimes(1));
    expect(studioMocks.startRun.mock.calls[0][4]).toMatch(/^chat-/);
    expect(await screen.findByText(/Ocean currents move heat/)).toBeInTheDocument();
    fireEvent.click(screen.getByText("Page 9"));
    expect(screen.getByText(/ocean transports heat/)).toBeInTheDocument();
  });

  it("restores conversation after refresh and opens Teacher-only sanitized trace", async () => {
    studioMocks.getLatestConversation.mockResolvedValue(answeredConversation);
    studioMocks.getTrace.mockResolvedValue({
      run_id: "run-1",
      result_type: "ANSWERED",
      nodes: [
        {
          node_name: "PRIVACY_CHECK",
          sequence: 1,
          status: "PASSED",
          duration_ms: 0,
          safe_summary: { provider_called: false },
        },
      ],
      models: {
        online: "gpt-4o-mini-2024-07-18",
        moderation: "omni-moderation-latest",
        embedding: "text-embedding-3-small",
      },
      usage: { input_tokens: 20, output_tokens: 10, total_ms: 700 },
      error_code: null,
    });
    render(
      <PlaygroundPanel role="TEACHER" csrf="csrf" version={version} onSessionExpired={vi.fn()} />,
    );

    expect(await screen.findByText(/Ocean currents move heat/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Inspect sanitized trace" }));
    expect(await screen.findByRole("complementary", { name: "Sanitized run trace" })).toBeInTheDocument();
    expect(screen.getByText("gpt-4o-mini-2024-07-18")).toBeInTheDocument();
    expect(screen.queryByText("How do currents affect climate?", { selector: "pre" })).not.toBeInTheDocument();
  });

  it("fills safety prompts without running them and shows a safe retry only for transient errors", async () => {
    studioMocks.getLatestConversation.mockResolvedValue(null);
    studioMocks.startRun.mockRejectedValueOnce(
      new ApiError("The model service is temporarily unavailable.", 503, "PROVIDER_UNAVAILABLE", null, true),
    );
    render(
      <PlaygroundPanel role="STUDENT" csrf="csrf" version={version} onSessionExpired={vi.fn()} />,
    );

    const input = await screen.findByLabelText("Message Ocean Explorer");
    await waitFor(() => expect(input).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "Privacy boundary" }));
    await waitFor(() =>
      expect(input).toHaveValue(
        "My home address is 742 Evergreen Street. Can you remember it?",
      ),
    );
    expect(studioMocks.startRun).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: /Send question/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("temporarily unavailable");
    expect(screen.getByRole("button", { name: "Retry safely" })).toBeInTheDocument();
  });
});
