import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { VersionDetail } from "@/lib/api";

import { KnowledgePanel } from "./knowledge-panel";

const studioMocks = vi.hoisted(() => ({
  uploadKnowledge: vi.fn(),
  getIngestionJob: vi.fn(),
  getVersion: vi.fn(),
  retryIngestion: vi.fn(),
  deleteKnowledge: vi.fn(),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, studioApi: { ...original.studioApi, ...studioMocks } };
});

const baseVersion: VersionDetail = {
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

const readyDocument = {
  id: "document-ready",
  original_filename: "ocean-literacy.pdf",
  status: "READY",
  page_count: 13,
  chunk_count: 48,
  sha256: "a".repeat(64),
  embedding_model: "text-embedding-3-small",
  ready_at: "2026-08-06T10:01:00Z",
};

afterEach(() => vi.clearAllMocks());

describe("KnowledgePanel", () => {
  it("rejects an unsupported file before making a request", () => {
    render(
      <KnowledgePanel
        role="STUDENT"
        csrf="csrf"
        version={baseVersion}
        onVersionChange={vi.fn()}
        onSessionExpired={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByLabelText("Choose file"), {
      target: { files: [new File(["notes"], "notes.docx")] },
    });
    expect(screen.getByRole("status")).toHaveTextContent("PDF, TXT, or Markdown");
    expect(studioMocks.uploadKnowledge).not.toHaveBeenCalled();
  });

  it("uploads a valid source and restores the server Ready state", async () => {
    const readyVersion: VersionDetail = {
      ...baseVersion,
      active_document_id: readyDocument.id,
      knowledge_status: "READY",
      knowledge: {
        active_document: readyDocument,
        latest_job: {
          id: "job-1",
          document_id: readyDocument.id,
          state: "READY",
          progress: { completed: 2, total: 2 },
          safe_error: null,
          error_code: null,
          retryable: false,
          updated_at: "2026-08-06T10:01:00Z",
        },
      },
    };
    const onVersionChange = vi.fn();
    studioMocks.uploadKnowledge.mockResolvedValue({
      document_id: readyDocument.id,
      job_id: "job-1",
      state: "UPLOADED",
      duplicate: false,
    });
    studioMocks.getVersion.mockResolvedValue(readyVersion);
    render(
      <KnowledgePanel
        role="STUDENT"
        csrf="csrf"
        version={baseVersion}
        onVersionChange={onVersionChange}
        onSessionExpired={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText("Choose file"), {
      target: { files: [new File(["ocean climate evidence"], "notes.md", { type: "text/markdown" })] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Use this source" }));

    await waitFor(() => expect(studioMocks.uploadKnowledge).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(onVersionChange).toHaveBeenCalledWith(readyVersion));
    expect(studioMocks.uploadKnowledge.mock.calls[0][3]).toMatch(/^upload-/);
  });

  it("refreshes the Version after polling reaches a terminal state", async () => {
    const activeJob = {
      id: "job-polling",
      document_id: readyDocument.id,
      state: "EMBEDDING" as const,
      progress: { completed: 1, total: 2 },
      safe_error: null,
      error_code: null,
      retryable: false,
      updated_at: "2026-08-06T10:00:30Z",
    };
    const processingVersion: VersionDetail = {
      ...baseVersion,
      knowledge_status: "PROCESSING",
      knowledge: { active_document: null, latest_job: activeJob },
    };
    const readyVersion: VersionDetail = {
      ...baseVersion,
      active_document_id: readyDocument.id,
      knowledge_status: "READY",
      knowledge: { active_document: readyDocument, latest_job: { ...activeJob, state: "READY" } },
    };
    const onVersionChange = vi.fn();
    studioMocks.getIngestionJob.mockResolvedValue({ ...activeJob, state: "READY" });
    studioMocks.getVersion.mockResolvedValue(readyVersion);
    render(
      <KnowledgePanel
        role="STUDENT"
        csrf="csrf"
        version={processingVersion}
        onVersionChange={onVersionChange}
        onSessionExpired={vi.fn()}
      />,
    );

    await waitFor(() => expect(studioMocks.getVersion).toHaveBeenCalledWith("version-1"));
    await waitFor(() => expect(onVersionChange).toHaveBeenCalledWith(readyVersion));
  });

  it("shows a failed replacement without hiding the previous Ready source and retries", async () => {
    const failedVersion: VersionDetail = {
      ...baseVersion,
      active_document_id: readyDocument.id,
      knowledge_status: "FAILED",
      knowledge: {
        active_document: readyDocument,
        latest_job: {
          id: "job-failed",
          document_id: "replacement-document",
          state: "FAILED",
          progress: { completed: 1, total: 2 },
          safe_error: "Embedding service failed. Retry this upload.",
          error_code: "EMBEDDING_PROVIDER_FAILED",
          retryable: true,
          updated_at: "2026-08-06T10:02:00Z",
        },
      },
    };
    studioMocks.retryIngestion.mockResolvedValue({
      document_id: "replacement-document",
      job_id: "job-retry",
      state: "UPLOADED",
      duplicate: false,
    });
    studioMocks.getVersion.mockResolvedValue(failedVersion);
    render(
      <KnowledgePanel
        role="STUDENT"
        csrf="csrf"
        version={failedVersion}
        onVersionChange={vi.fn()}
        onSessionExpired={vi.fn()}
      />,
    );

    expect(screen.getByText("ocean-literacy.pdf")).toBeInTheDocument();
    expect(screen.getByText(/previous Ready source remains active/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(studioMocks.retryIngestion).toHaveBeenCalledWith("job-failed", "csrf"));
  });

  it("keeps source controls read-only in Teacher view", () => {
    render(
      <KnowledgePanel
        role="TEACHER"
        csrf="csrf"
        version={{ ...baseVersion, allowed_actions: [] }}
        onVersionChange={vi.fn()}
        onSessionExpired={vi.fn()}
      />,
    );
    expect(screen.getByText(/Teacher view shows evidence status/i)).toBeInTheDocument();
    expect(screen.getByLabelText("Choose file")).toBeDisabled();
  });
});
