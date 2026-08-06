const DEFAULT_API_BASE_URL = "http://localhost:8000";
const REQUEST_TIMEOUT_MS = 8_000;

export type Role = "STUDENT" | "TEACHER";
export type AudienceAge = "AGE_7_11" | "AGE_12_17";
export type Tone = "FRIENDLY" | "CURIOUS" | "COACH_LIKE";
export type ResponseLength = "SHORT" | "BALANCED";
export type KnowledgeStatus = "NOT_ADDED" | "PROCESSING" | "READY" | "FAILED";
export type IngestionState =
  | "UPLOADED"
  | "EXTRACTING"
  | "CHUNKING"
  | "EMBEDDING"
  | "READY"
  | "FAILED";

export type HealthResponse = { status: "ok"; service: "agentsprout-api" };
export type ReadinessCheck = "ok" | "failed";
export type ReadinessResponse = {
  status: "ready" | "not_ready";
  checks: Record<"sqlite" | "chroma" | "uploads" | "migrations", ReadinessCheck>;
};

export type SessionResponse = {
  session: { role: Role; expires_at: string };
  csrf_token: string;
};

export type AgentFields = {
  project_name: string;
  problem_to_solve: string;
  intended_users: string;
  audience_age: AudienceAge;
  success_goal: string;
  welcome_message: string;
  tone: Tone;
  response_length: ResponseLength;
  custom_instructions: string;
};

export type AgentCreate = AgentFields & { template: "KNOWLEDGE_EXPLORER" };
export type VersionSummary = {
  id: string;
  number: number;
  state: "DRAFT" | "IN_REVIEW" | "CHANGES_REQUESTED" | "APPROVED" | "PUBLISHED" | "WITHDRAWN";
  knowledge_status: KnowledgeStatus;
};
export type AgentSummary = {
  id: string;
  display_name: string;
  slug: string;
  current_version: VersionSummary;
  published_version: VersionSummary | null;
  allowed_actions: string[];
  next_action: string;
};
export type AgentAggregate = {
  id: string;
  display_name: string;
  slug: string;
  current_draft_version_id: string | null;
  published_version_id: string | null;
  versions: VersionSummary[];
  allowed_actions: string[];
};
export type VersionDetail = AgentFields & {
  id: string;
  agent_id: string;
  version_number: number;
  state: VersionSummary["state"];
  active_document_id: string | null;
  knowledge_status: KnowledgeStatus;
  knowledge: KnowledgeView;
  what_changed: string | null;
  why_changed: string | null;
  source_version_id: string | null;
  submitted_at: string | null;
  approved_at: string | null;
  reviews: TeacherReview[];
  allowed_actions: string[];
  created_at: string;
  updated_at: string;
};
export type TeacherReview = {
  id: string;
  evaluation_run_id: string;
  decision: "REQUEST_CHANGES" | "APPROVE" | "PUBLISH" | "WITHDRAW";
  feedback: string | null;
  created_at: string;
};

export type IngestionJob = {
  id: string;
  document_id: string;
  state: IngestionState;
  progress: { completed: number; total: number };
  safe_error: string | null;
  error_code: string | null;
  retryable: boolean;
  updated_at: string;
};

export type KnowledgeDocument = {
  id: string;
  original_filename: string;
  status: string;
  page_count: number | null;
  chunk_count: number | null;
  sha256: string;
  embedding_model: string;
  ready_at: string | null;
};

export type KnowledgeView = {
  active_document: KnowledgeDocument | null;
  latest_job: IngestionJob | null;
};

export type KnowledgeUploadResponse = {
  document_id: string;
  job_id: string;
  state: IngestionState;
  duplicate: boolean;
};

export type ChatPhase =
  | "QUEUED"
  | "PRIVACY_CHECK"
  | "MODERATION"
  | "INTENT_CLASSIFICATION"
  | "RETRIEVAL"
  | "GENERATION"
  | "OUTPUT_VALIDATION"
  | "COMPLETED"
  | "FAILED";
export type ChatResultType = "ANSWERED" | "BLOCKED" | "GUIDED" | "REFUSED" | "FAILED";
export type Citation = {
  chunk_id: string;
  filename: string;
  page_number: number;
  excerpt: string;
};
export type ChatResult = { type: ChatResultType; answer: string; citations: Citation[] };
export type ChatRun = {
  id: string;
  conversation_id: string;
  phase: ChatPhase;
  status: "RUNNING" | "COMPLETED" | "FAILED";
  display_stage: string;
  result: ChatResult | null;
  safe_error: string | null;
  retryable: boolean;
};
export type ConversationMessage = {
  id: string;
  run_id: string | null;
  role: "USER" | "ASSISTANT";
  content: string;
  result_type: ChatResultType | null;
  citations: Citation[];
  created_at: string;
};
export type Conversation = {
  id: string;
  version_id: string;
  messages: ConversationMessage[];
  updated_at: string;
};
export type ChatTrace = {
  run_id: string;
  result_type: ChatResultType | null;
  nodes: Array<{
    node_name: string;
    sequence: number;
    status: string;
    duration_ms: number;
    safe_summary: Record<string, unknown>;
  }>;
  models: Record<"online" | "moderation" | "embedding", string>;
  usage: Record<string, number>;
  error_code: string | null;
};

export type EvaluationState = "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED";
export type EvaluationCategory =
  | "KNOWLEDGE"
  | "OUT_OF_KNOWLEDGE"
  | "PRIVACY"
  | "HOMEWORK"
  | "INJECTION"
  | "AGE";
export type EvaluationRun = {
  id: string;
  version_id: string;
  state: EvaluationState;
  progress: { completed: number; total: number; passed: number; failed: number; errors: number };
  models: Record<"online" | "judge" | "embedding" | "moderation", string>;
  metrics: { grounded_pass_rate: number; age_average: number; instruction_average: number } | null;
  usage: { input_tokens: number; output_tokens: number; estimated_cost_usd: number };
  release_eligible: boolean;
  safe_error: string | null;
  created_at: string;
  finished_at: string | null;
};
export type EvaluationCase = {
  id: string;
  case_key: string;
  category: EvaluationCategory;
  safe_prompt: string;
  expected_result_type: ChatResultType;
  actual_result_type: ChatResultType | null;
  state: string;
  passed: boolean;
  blocking: boolean;
  safe_error_code: string | null;
};
export type EvaluationCaseDetail = EvaluationCase & {
  deterministic_checks: Record<string, boolean>;
  evidence: Array<Record<string, unknown>>;
  judge: Record<string, string | number> | null;
  usage: Record<string, number>;
  latency_ms: number;
  trace_run_id: string | null;
};
export type VersionComparison = {
  left: { version_id: string; version_number: number; run_id: string; release_eligible: boolean };
  right: { version_id: string; version_number: number; run_id: string; release_eligible: boolean };
  deltas: Record<"grounded_pass_rate" | "age_average" | "instruction_average" | "latency_ms" | "input_tokens" | "output_tokens" | "estimated_cost_usd", number>;
  categories: Array<{ category: EvaluationCategory; left_passed: number; left_total: number; right_passed: number; right_total: number; passed_delta: number }>;
  cases: Array<{ case_key: string; category: EvaluationCategory; left_passed: boolean; right_passed: boolean; transition: "IMPROVED" | "REGRESSED" | "UNCHANGED" }>;
};

export type PublicAgent = {
  slug: string;
  project_name: string;
  problem_to_solve: string;
  intended_users: string;
  audience_age: AudienceAge;
  success_goal: string;
  welcome_message: string;
  version_number: number;
  status: "PUBLISHED";
  builder_label: "Student Builder";
  knowledge_source: Record<"title" | "author" | "license" | "source_url", string>;
};
export type PublicRun = Omit<ChatRun, "conversation_id">;

type ErrorEnvelope = {
  error?: {
    code?: string;
    message?: string;
    request_id?: string;
    retryable?: boolean;
    retry_after_seconds?: number | null;
    field_errors?: Record<string, string>;
  };
};

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number | null,
    readonly code: string,
    readonly requestId: string | null,
    readonly retryable: boolean,
    readonly retryAfterSeconds: number | null = null,
    readonly fieldErrors: Record<string, string> = {},
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function apiBaseUrl(): string {
  return (process.env.NEXT_PUBLIC_API_BASE_URL ?? DEFAULT_API_BASE_URL).replace(/\/$/, "");
}

async function parseError(response: Response): Promise<ApiError> {
  let body: ErrorEnvelope = {};
  try {
    body = (await response.json()) as ErrorEnvelope;
  } catch {
    // Normalize non-JSON upstream failures to safe product copy.
  }
  return new ApiError(
    body.error?.message ?? "AgentSprout could not reach the service.",
    response.status,
    body.error?.code ?? "API_ERROR",
    body.error?.request_id ?? response.headers.get("X-Request-ID"),
    body.error?.retryable ?? response.status >= 500,
    body.error?.retry_after_seconds ?? null,
    body.error?.field_errors ?? {},
  );
}

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  csrfToken?: string;
  idempotencyKey?: string;
  signal?: AbortSignal;
  acceptedStatuses?: readonly number[];
  publicRunToken?: string;
  includeCredentials?: boolean;
};

async function requestJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const timeoutSignal = AbortSignal.timeout(REQUEST_TIMEOUT_MS);
  const combinedSignal = options.signal
    ? AbortSignal.any([options.signal, timeoutSignal])
    : timeoutSignal;
  const headers: Record<string, string> = { Accept: "application/json" };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (options.csrfToken) headers["X-CSRF-Token"] = options.csrfToken;
  if (options.idempotencyKey) headers["Idempotency-Key"] = options.idempotencyKey;
  if (options.publicRunToken) headers["X-Public-Run-Token"] = options.publicRunToken;

  try {
    const response = await fetch(`${apiBaseUrl()}${path}`, {
      method: options.method ?? "GET",
      headers,
      credentials: options.includeCredentials === false ? "omit" : "include",
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: combinedSignal,
    });
    if (!response.ok && !options.acceptedStatuses?.includes(response.status)) {
      throw await parseError(response);
    }
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && ["TimeoutError", "AbortError"].includes(error.name)) {
      const abortedByCaller = options.signal?.aborted ?? false;
      throw new ApiError(
        abortedByCaller ? "The request was cancelled." : "The request timed out. Try again.",
        null,
        abortedByCaller ? "CANCELLED" : "TIMEOUT",
        null,
        !abortedByCaller,
      );
    }
    throw new ApiError("The backend is offline or unreachable.", null, "NETWORK_ERROR", null, true);
  }
}

async function requestForm<T>(
  path: string,
  form: FormData,
  csrfToken: string,
  idempotencyKey: string,
): Promise<T> {
  const timeoutSignal = AbortSignal.timeout(20_000);
  try {
    const response = await fetch(`${apiBaseUrl()}${path}`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "X-CSRF-Token": csrfToken,
        "Idempotency-Key": idempotencyKey,
      },
      credentials: "include",
      body: form,
      signal: timeoutSignal,
    });
    if (!response.ok) throw await parseError(response);
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && ["TimeoutError", "AbortError"].includes(error.name)) {
      throw new ApiError("The upload timed out. Try again.", null, "TIMEOUT", null, true);
    }
    throw new ApiError("The backend is offline or unreachable.", null, "NETWORK_ERROR", null, true);
  }
}

export const systemApi = {
  health: (signal?: AbortSignal) => requestJson<HealthResponse>("/api/v1/health", { signal }),
  readiness: (signal?: AbortSignal) =>
    requestJson<ReadinessResponse>("/api/v1/ready", { signal, acceptedStatuses: [503] }),
};

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
  createNextVersion: (versionId: string, whatChanged: string, whyChanged: string, csrfToken: string, idempotencyKey: string) =>
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
  compareVersions: (leftVersionId: string, rightVersionId: string, leftRunId: string, rightRunId: string, signal?: AbortSignal) =>
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

export const publicApi = {
  getAgent: (slug: string, signal?: AbortSignal) =>
    requestJson<PublicAgent>(`/api/v1/public/agents/${encodeURIComponent(slug)}`, {
      signal,
      includeCredentials: false,
    }),
  startRun: (slug: string, message: string, idempotencyKey: string) =>
    requestJson<{ run_id: string; run_token: string; phase: ChatPhase; poll_after_ms: number }>(
      `/api/v1/public/agents/${encodeURIComponent(slug)}/runs`,
      { method: "POST", body: { message }, idempotencyKey, includeCredentials: false },
    ),
  getRun: (runId: string, runToken: string, signal?: AbortSignal) =>
    requestJson<PublicRun>(`/api/v1/public/runs/${runId}`, {
      signal,
      publicRunToken: runToken,
      includeCredentials: false,
    }),
};
