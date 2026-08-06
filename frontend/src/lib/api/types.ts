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
