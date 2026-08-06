import { requestForm, requestJson } from "./client";
import type {
  AgentAggregate,
  AgentCreate,
  AgentFields,
  AgentSummary,
  ChatPhase,
  ChatRun,
  ChatTrace,
  Conversation,
  EvaluationCase,
  EvaluationCaseDetail,
  EvaluationCategory,
  EvaluationRun,
  EvaluationState,
  IngestionJob,
  KnowledgeUploadResponse,
  Role,
  SessionResponse,
  TeacherReview,
  VersionComparison,
  VersionDetail,
} from "./types";

export const studioApi = {
  access: (accessCode: string) =>
    requestJson<SessionResponse>("/api/v1/studio/access", {
      method: "POST",
      body: { access_code: accessCode },
    }),
  restore: (signal?: AbortSignal) =>
    requestJson<SessionResponse>("/api/v1/studio/session", { signal }),
  changeRole: (role: Role, csrfToken: string) =>
    requestJson<SessionResponse>("/api/v1/studio/session/role", {
      method: "PATCH",
      body: { role },
      csrfToken,
    }),
  signOut: (csrfToken: string) =>
    requestJson<void>("/api/v1/studio/session", { method: "DELETE", csrfToken }),
  listAgents: (signal?: AbortSignal) =>
    requestJson<{ agents: AgentSummary[] }>("/api/v1/studio/agents", { signal }),
  createAgent: (payload: AgentCreate, csrfToken: string, idempotencyKey: string) =>
    requestJson<{ agent: AgentAggregate; version: VersionDetail }>("/api/v1/studio/agents", {
      method: "POST",
      body: payload,
      csrfToken,
      idempotencyKey,
    }),
  getAgent: (agentId: string, signal?: AbortSignal) =>
    requestJson<AgentAggregate>(`/api/v1/studio/agents/${agentId}`, { signal }),
  getVersion: (versionId: string, signal?: AbortSignal) =>
    requestJson<VersionDetail>(`/api/v1/studio/versions/${versionId}`, { signal }),
  updateVersion: (versionId: string, payload: Partial<AgentFields>, csrfToken: string) =>
    requestJson<VersionDetail>(`/api/v1/studio/versions/${versionId}`, {
      method: "PATCH",
      body: payload,
      csrfToken,
    }),
  submitVersion: (versionId: string, csrfToken: string, idempotencyKey: string) =>
    requestJson<VersionDetail>(`/api/v1/studio/versions/${versionId}/submit`, {
      method: "POST",
      csrfToken,
      idempotencyKey,
    }),
  uploadKnowledge: (versionId: string, file: File, csrfToken: string, idempotencyKey: string) => {
    const form = new FormData();
    form.append("file", file);
    return requestForm<KnowledgeUploadResponse>(
      `/api/v1/studio/versions/${versionId}/knowledge`,
      form,
      csrfToken,
      idempotencyKey,
    );
  },
  getIngestionJob: (jobId: string, signal?: AbortSignal) =>
    requestJson<IngestionJob>(`/api/v1/studio/ingestion-jobs/${jobId}`, { signal }),
  retryIngestion: (jobId: string, csrfToken: string) =>
    requestJson<KnowledgeUploadResponse>(`/api/v1/studio/ingestion-jobs/${jobId}/retry`, {
      method: "POST",
      csrfToken,
    }),
  deleteKnowledge: (versionId: string, documentId: string, csrfToken: string) =>
    requestJson<void>(`/api/v1/studio/versions/${versionId}/knowledge/${documentId}`, {
      method: "DELETE",
      csrfToken,
    }),
  startRun: (
    versionId: string,
    message: string,
    conversationId: string | null,
    csrfToken: string,
    idempotencyKey: string,
  ) =>
    requestJson<{
      run_id: string;
      conversation_id: string;
      phase: ChatPhase;
      poll_after_ms: number;
    }>(`/api/v1/studio/versions/${versionId}/runs`, {
      method: "POST",
      body: { message, conversation_id: conversationId },
      csrfToken,
      idempotencyKey,
    }),
  getRun: (runId: string, signal?: AbortSignal) =>
    requestJson<ChatRun>(`/api/v1/studio/runs/${runId}`, { signal }),
  getConversation: (conversationId: string, signal?: AbortSignal) =>
    requestJson<Conversation>(`/api/v1/studio/conversations/${conversationId}`, { signal }),
  getLatestConversation: (versionId: string, signal?: AbortSignal) =>
    requestJson<Conversation | null>(`/api/v1/studio/versions/${versionId}/conversation`, {
      signal,
    }),
  getTrace: (runId: string, signal?: AbortSignal) =>
    requestJson<ChatTrace>(`/api/v1/studio/runs/${runId}/trace`, { signal }),
  startEvaluation: (versionId: string, csrfToken: string, idempotencyKey: string) =>
    requestJson<{ evaluation_run_id: string; state: EvaluationState; total_cases: number }>(
      `/api/v1/studio/versions/${versionId}/evaluations`,
      { method: "POST", csrfToken, idempotencyKey },
    ),
  getEvaluation: (runId: string, signal?: AbortSignal) =>
    requestJson<EvaluationRun>(`/api/v1/studio/evaluations/${runId}`, { signal }),
  listEvaluations: (versionId: string, signal?: AbortSignal) =>
    requestJson<{ evaluations: EvaluationRun[] }>(
      `/api/v1/studio/versions/${versionId}/evaluations`,
      { signal },
    ),
  getEvaluationCases: (runId: string, category?: EvaluationCategory, signal?: AbortSignal) =>
    requestJson<{ cases: EvaluationCase[] }>(
      `/api/v1/studio/evaluations/${runId}/cases${category ? `?category=${category}` : ""}`,
      { signal },
    ),
  getEvaluationCase: (resultId: string, signal?: AbortSignal) =>
    requestJson<EvaluationCaseDetail>(`/api/v1/studio/evaluation-cases/${resultId}`, { signal }),
  requestChanges: (versionId: string, evaluationRunId: string, feedback: string, csrfToken: string) =>
    requestJson<{ version: VersionDetail; review: TeacherReview }>(
      `/api/v1/studio/versions/${versionId}/request-changes`,
      { method: "POST", body: { evaluation_run_id: evaluationRunId, feedback }, csrfToken },
    ),
  createNextVersion: (
    versionId: string,
    whatChanged: string,
    whyChanged: string,
    csrfToken: string,
    idempotencyKey: string,
  ) =>
    requestJson<VersionDetail>(`/api/v1/studio/versions/${versionId}/next-version`, {
      method: "POST",
      body: { what_changed: whatChanged, why_changed: whyChanged },
      csrfToken,
      idempotencyKey,
    }),
  approveVersion: (versionId: string, evaluationRunId: string, csrfToken: string) =>
    requestJson<{ version: VersionDetail; review: TeacherReview }>(
      `/api/v1/studio/versions/${versionId}/approve`,
      { method: "POST", body: { evaluation_run_id: evaluationRunId }, csrfToken },
    ),
  compareVersions: (
    leftVersionId: string,
    rightVersionId: string,
    leftRunId: string,
    rightRunId: string,
    signal?: AbortSignal,
  ) =>
    requestJson<VersionComparison>(
      `/api/v1/studio/versions/${leftVersionId}/compare/${rightVersionId}?left_run_id=${encodeURIComponent(leftRunId)}&right_run_id=${encodeURIComponent(rightRunId)}`,
      { signal },
    ),
  publishVersion: (versionId: string, slug: string, csrfToken: string, idempotencyKey: string) =>
    requestJson<{ slug: string; public_path: string; version_number: number }>(
      `/api/v1/studio/versions/${versionId}/publish`,
      { method: "POST", body: { slug }, csrfToken, idempotencyKey },
    ),
  withdrawVersion: (versionId: string, csrfToken: string, idempotencyKey: string) =>
    requestJson<{ slug: string; public_path: string; version_number: number }>(
      `/api/v1/studio/versions/${versionId}/withdraw`,
      { method: "POST", csrfToken, idempotencyKey },
    ),
};
