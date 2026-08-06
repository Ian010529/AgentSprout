from __future__ import annotations

import unicodedata
from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.enums import (
    AgentTemplate,
    AudienceAge,
    ChatPhase,
    ChatResultType,
    ChatStatus,
    EvaluationCategory,
    EvaluationState,
    IngestionState,
    ResponseLength,
    Role,
    Tone,
    VersionState,
)

KnowledgeStatus = Literal["NOT_ADDED", "PROCESSING", "READY", "FAILED"]


def clean_text(value: str) -> str:
    cleaned = value.strip()
    if any(unicodedata.category(char).startswith("C") and char not in "\n\r\t" for char in cleaned):
        raise ValueError("Control characters are not allowed")
    return cleaned


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AccessRequest(StrictModel):
    access_code: str = Field(min_length=1, max_length=256)


class SessionView(StrictModel):
    role: Role
    expires_at: datetime


class SessionResponse(StrictModel):
    session: SessionView
    csrf_token: str


class RoleUpdate(StrictModel):
    role: Role


class AgentFields(StrictModel):
    project_name: Annotated[str, Field(min_length=3, max_length=80)]
    problem_to_solve: Annotated[str, Field(min_length=10, max_length=500)]
    intended_users: Annotated[str, Field(min_length=3, max_length=240)]
    audience_age: AudienceAge
    success_goal: Annotated[str, Field(min_length=10, max_length=300)]
    welcome_message: Annotated[str, Field(min_length=3, max_length=240)]
    tone: Tone
    response_length: ResponseLength
    custom_instructions: Annotated[str, Field(max_length=500)] = ""

    @field_validator(
        "project_name",
        "problem_to_solve",
        "intended_users",
        "success_goal",
        "welcome_message",
        "custom_instructions",
    )
    @classmethod
    def validate_text(cls, value: str) -> str:
        return clean_text(value)


class AgentCreate(AgentFields):
    template: AgentTemplate


class AgentVersionPatch(StrictModel):
    project_name: Annotated[str | None, Field(min_length=3, max_length=80)] = None
    problem_to_solve: Annotated[str | None, Field(min_length=10, max_length=500)] = None
    intended_users: Annotated[str | None, Field(min_length=3, max_length=240)] = None
    audience_age: AudienceAge | None = None
    success_goal: Annotated[str | None, Field(min_length=10, max_length=300)] = None
    welcome_message: Annotated[str | None, Field(min_length=3, max_length=240)] = None
    tone: Tone | None = None
    response_length: ResponseLength | None = None
    custom_instructions: Annotated[str | None, Field(max_length=500)] = None

    @field_validator(
        "project_name",
        "problem_to_solve",
        "intended_users",
        "success_goal",
        "welcome_message",
        "custom_instructions",
    )
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        return clean_text(value) if value is not None else None

    @model_validator(mode="after")
    def require_update(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one editable field is required")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Editable fields cannot be null")
        return self


class VersionSummary(StrictModel):
    id: str
    number: int
    state: VersionState
    knowledge_status: KnowledgeStatus = "NOT_ADDED"


class AgentSummary(StrictModel):
    id: str
    display_name: str
    current_version: VersionSummary
    allowed_actions: list[str]
    next_action: str


class AgentListResponse(StrictModel):
    agents: list[AgentSummary]


class AgentAggregate(StrictModel):
    id: str
    display_name: str
    slug: str
    current_draft_version_id: str | None
    published_version_id: str | None
    versions: list[VersionSummary]
    allowed_actions: list[str]


class JobProgress(StrictModel):
    completed: int
    total: int


class IngestionJobView(StrictModel):
    id: str
    document_id: str
    state: IngestionState
    progress: JobProgress
    safe_error: str | None
    error_code: str | None
    retryable: bool
    updated_at: datetime


class KnowledgeDocumentView(StrictModel):
    id: str
    original_filename: str
    status: str
    page_count: int | None
    chunk_count: int | None
    sha256: str
    embedding_model: str
    ready_at: datetime | None


class KnowledgeView(StrictModel):
    active_document: KnowledgeDocumentView | None
    latest_job: IngestionJobView | None


class TeacherReviewView(StrictModel):
    id: str
    evaluation_run_id: str
    decision: Literal["REQUEST_CHANGES", "APPROVE", "PUBLISH", "WITHDRAW"]
    feedback: str | None
    created_at: datetime


class VersionDetail(AgentFields):
    id: str
    agent_id: str
    version_number: int
    state: VersionState
    active_document_id: str | None
    knowledge_status: KnowledgeStatus = "NOT_ADDED"
    knowledge: KnowledgeView
    what_changed: str | None
    why_changed: str | None
    source_version_id: str | None
    submitted_at: datetime | None
    approved_at: datetime | None
    reviews: list[TeacherReviewView]
    allowed_actions: list[str]
    created_at: datetime
    updated_at: datetime


class ReviewDecisionResponse(StrictModel):
    version: VersionDetail
    review: TeacherReviewView


class RequestChanges(StrictModel):
    evaluation_run_id: str = Field(min_length=36, max_length=36)
    feedback: Annotated[str, Field(min_length=3, max_length=1000)]

    @field_validator("feedback")
    @classmethod
    def validate_feedback(cls, value: str) -> str:
        return clean_text(value)


class ApproveVersion(StrictModel):
    evaluation_run_id: str = Field(min_length=36, max_length=36)


class NextVersion(StrictModel):
    what_changed: Annotated[str, Field(min_length=3, max_length=500)]
    why_changed: Annotated[str, Field(min_length=3, max_length=500)]

    @field_validator("what_changed", "why_changed")
    @classmethod
    def validate_reflection(cls, value: str) -> str:
        return clean_text(value)


class ComparisonSide(StrictModel):
    version_id: str
    version_number: int
    run_id: str
    release_eligible: bool


class ComparisonCategory(StrictModel):
    category: EvaluationCategory
    left_passed: int
    left_total: int
    right_passed: int
    right_total: int
    passed_delta: int


class ComparisonCase(StrictModel):
    case_key: str
    category: EvaluationCategory
    left_passed: bool
    right_passed: bool
    transition: Literal["IMPROVED", "REGRESSED", "UNCHANGED"]


class VersionComparison(StrictModel):
    left: ComparisonSide
    right: ComparisonSide
    deltas: dict[str, int | float]
    categories: list[ComparisonCategory]
    cases: list[ComparisonCase]


class PublishVersion(StrictModel):
    slug: Annotated[str, Field(min_length=3, max_length=60, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")]


class PublishResponse(StrictModel):
    slug: str
    public_path: str
    version_number: int


class PublicAgentView(StrictModel):
    slug: str
    project_name: str
    problem_to_solve: str
    intended_users: str
    audience_age: AudienceAge
    success_goal: str
    welcome_message: str
    version_number: int
    status: Literal["PUBLISHED"]
    builder_label: Literal["Student Builder"] = "Student Builder"
    knowledge_source: dict[str, str]


class PublicRunCreate(StrictModel):
    message: Annotated[str, Field(min_length=1, max_length=1000)]

    @field_validator("message")
    @classmethod
    def validate_public_message(cls, value: str) -> str:
        return clean_text(value)


class PublicRunCreateResponse(StrictModel):
    run_id: str
    run_token: str
    phase: ChatPhase
    poll_after_ms: int = 500


class ResetResponse(StrictModel):
    reset_audit_id: str
    deleted_agents: int
    preserved_fixed_samples: int


class FixedSampleResponse(StrictModel):
    agent_id: str
    slug: str
    fixed: Literal[True] = True


class AgentCreateResponse(StrictModel):
    agent: AgentAggregate
    version: VersionDetail


class KnowledgeUploadResponse(StrictModel):
    document_id: str
    job_id: str
    state: IngestionState
    duplicate: bool


class ChatRunCreate(StrictModel):
    message: Annotated[str, Field(min_length=1, max_length=1000)]
    conversation_id: str | None = Field(default=None, min_length=36, max_length=36)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        return clean_text(value)


class ChatRunCreateResponse(StrictModel):
    run_id: str
    conversation_id: str
    phase: ChatPhase
    poll_after_ms: int = 500


class CitationView(StrictModel):
    chunk_id: str
    filename: str
    page_number: int
    excerpt: str


class ChatResultView(StrictModel):
    type: ChatResultType
    answer: str
    citations: list[CitationView]


class PublicRunView(StrictModel):
    id: str
    phase: ChatPhase
    status: ChatStatus
    display_stage: str
    result: ChatResultView | None
    safe_error: str | None
    retryable: bool


class ChatRunView(StrictModel):
    id: str
    conversation_id: str
    phase: ChatPhase
    status: ChatStatus
    display_stage: str
    result: ChatResultView | None
    safe_error: str | None
    retryable: bool = False


class ConversationMessageView(StrictModel):
    id: str
    run_id: str | None
    role: Literal["USER", "ASSISTANT"]
    content: str
    result_type: ChatResultType | None
    citations: list[CitationView]
    created_at: datetime


class ConversationView(StrictModel):
    id: str
    version_id: str
    messages: list[ConversationMessageView]
    updated_at: datetime


class TraceNodeView(StrictModel):
    node_name: str
    sequence: int
    status: str
    duration_ms: int
    safe_summary: dict[str, object]


class ChatTraceView(StrictModel):
    run_id: str
    result_type: ChatResultType | None
    nodes: list[TraceNodeView]
    models: dict[str, str]
    usage: dict[str, int | float]
    error_code: str | None


class EvaluationCreateResponse(StrictModel):
    evaluation_run_id: str
    state: EvaluationState
    total_cases: int
    completed_cases: int
    poll_after_ms: int = 1000


class EvaluationProgress(StrictModel):
    completed: int
    total: int
    passed: int
    failed: int
    errors: int


class EvaluationRunView(StrictModel):
    id: str
    version_id: str
    state: EvaluationState
    progress: EvaluationProgress
    models: dict[str, str]
    metrics: dict[str, float] | None
    usage: dict[str, int | float]
    release_eligible: bool
    safe_error: str | None
    created_at: datetime
    finished_at: datetime | None


class EvaluationRunList(StrictModel):
    evaluations: list[EvaluationRunView]


class EvaluationCaseSummary(StrictModel):
    id: str
    case_key: str
    category: EvaluationCategory
    safe_prompt: str
    expected_result_type: ChatResultType
    actual_result_type: ChatResultType | None
    state: str
    passed: bool
    blocking: bool
    safe_error_code: str | None


class EvaluationCaseList(StrictModel):
    cases: list[EvaluationCaseSummary]


class EvaluationCaseDetail(EvaluationCaseSummary):
    deterministic_checks: dict[str, bool]
    evidence: list[dict[str, object]]
    judge: dict[str, int | str] | None
    usage: dict[str, int | float]
    latency_ms: int
    trace_run_id: str | None
