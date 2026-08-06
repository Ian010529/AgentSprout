from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DemoSession(Base):
    __tablename__ = "demo_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(80))
    current_draft_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    published_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentVersion(Base):
    __tablename__ = "agent_versions"
    __table_args__ = (UniqueConstraint("agent_id", "version_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(24), index=True)
    project_name: Mapped[str] = mapped_column(String(80))
    problem_to_solve: Mapped[str] = mapped_column(String(500))
    intended_users: Mapped[str] = mapped_column(String(240))
    audience_age: Mapped[str] = mapped_column(String(16))
    success_goal: Mapped[str] = mapped_column(String(300))
    welcome_message: Mapped[str] = mapped_column(String(240))
    tone: Mapped[str] = mapped_column(String(16))
    response_length: Mapped[str] = mapped_column(String(16))
    custom_instructions: Mapped[str] = mapped_column(String(500), default="")
    what_changed: Mapped[str | None] = mapped_column(String(500), nullable=True)
    why_changed: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    active_document_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str | None] = mapped_column(
        ForeignKey("demo_sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    actor_type: Mapped[str] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(64), index=True)
    target_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    result: Mapped[str] = mapped_column(String(24))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RateLimitBucket(Base):
    __tablename__ = "rate_limit_buckets"
    __table_args__ = (
        UniqueConstraint("subject_hash", "scope", "window_start"),
        Index("ix_rate_limit_lookup", "subject_hash", "scope", "window_end"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    subject_hash: Mapped[str] = mapped_column(String(64))
    scope: Mapped[str] = mapped_column(String(32))
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    count: Mapped[int] = mapped_column(Integer)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("session_id", "scope", "key_hash"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("demo_sessions.id", ondelete="CASCADE"), index=True
    )
    scope: Mapped[str] = mapped_column(String(48))
    key_hash: Mapped[str] = mapped_column(String(64))
    request_hash: Mapped[str] = mapped_column(String(64))
    response_status: Mapped[int] = mapped_column(Integer)
    response_body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = (
        Index("ix_knowledge_version_status", "version_id", "status"),
        UniqueConstraint("version_id", "sha256", name="uq_knowledge_version_sha256"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    version_id: Mapped[str] = mapped_column(
        ForeignKey("agent_versions.id", ondelete="CASCADE"), index=True
    )
    original_filename: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(80))
    extension: Mapped[str] = mapped_column(String(8))
    byte_size: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    storage_path: Mapped[str] = mapped_column(String(500), unique=True)
    status: Mapped[str] = mapped_column(String(16), index=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding_model: Mapped[str] = mapped_column(String(100))
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"
    __table_args__ = (UniqueConstraint("document_id", "attempt"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True
    )
    state: Mapped[str] = mapped_column(String(16), index=True)
    attempt: Mapped[int] = mapped_column(Integer)
    progress_completed: Mapped[int] = mapped_column(Integer, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    safe_error_message: Mapped[str | None] = mapped_column(String(240), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class StudioConversation(Base):
    __tablename__ = "studio_conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    version_id: Mapped[str] = mapped_column(
        ForeignKey("agent_versions.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ChatRun(Base):
    __tablename__ = "chat_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    version_id: Mapped[str] = mapped_column(
        ForeignKey("agent_versions.id", ondelete="CASCADE"), index=True
    )
    conversation_id: Mapped[str | None] = mapped_column(
        ForeignKey("studio_conversations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    surface: Mapped[str] = mapped_column(String(16))
    audience_age_override: Mapped[str | None] = mapped_column(String(16), nullable=True)
    phase: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(16), index=True)
    result_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    input_message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    output_message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    input_fingerprint: Mapped[str] = mapped_column(String(64))
    online_model: Mapped[str] = mapped_column(String(100))
    moderation_model: Mapped[str] = mapped_column(String(100))
    embedding_model: Mapped[str] = mapped_column(String(100))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    reasoning_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Numeric(12, 8), default=0)
    retrieval_ms: Mapped[int] = mapped_column(Integer, default=0)
    provider_ms: Mapped[int] = mapped_column(Integer, default=0)
    total_ms: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    safe_error_message: Mapped[str | None] = mapped_column(String(240), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("studio_conversations.id", ondelete="CASCADE"), index=True
    )
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("chat_runs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MessageCitation(Base):
    __tablename__ = "message_citations"
    __table_args__ = (UniqueConstraint("message_id", "chunk_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    message_id: Mapped[str] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), index=True
    )
    chunk_id: Mapped[str] = mapped_column(String(160))
    filename: Mapped[str] = mapped_column(String(255))
    page_number: Mapped[int] = mapped_column(Integer)
    excerpt: Mapped[str] = mapped_column(Text)
    rank: Mapped[int] = mapped_column(Integer)


class RunNodeTrace(Base):
    __tablename__ = "run_node_traces"
    __table_args__ = (UniqueConstraint("run_id", "sequence"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("chat_runs.id", ondelete="CASCADE"), index=True)
    node_name: Mapped[str] = mapped_column(String(48))
    sequence: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int] = mapped_column(Integer)
    safe_summary_json: Mapped[str] = mapped_column(Text)


class SafetyEvent(Base):
    __tablename__ = "safety_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("chat_runs.id", ondelete="CASCADE"), index=True)
    version_id: Mapped[str] = mapped_column(
        ForeignKey("agent_versions.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[str] = mapped_column(String(48))
    action: Mapped[str] = mapped_column(String(48))
    detector: Mapped[str] = mapped_column(String(48))
    safe_summary: Mapped[str] = mapped_column(String(240))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EvaluationCase(Base):
    __tablename__ = "evaluation_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_key: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    suite_version: Mapped[str] = mapped_column(String(48), index=True)
    category: Mapped[str] = mapped_column(String(32), index=True)
    prompt_template: Mapped[str] = mapped_column(Text)
    audience_age: Mapped[str] = mapped_column(String(16))
    expected_result_type: Mapped[str] = mapped_column(String(16))
    expected_pages_json: Mapped[str] = mapped_column(Text)
    rubric_version: Mapped[str] = mapped_column(String(48))
    enabled: Mapped[int] = mapped_column(Integer, default=1)


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    version_id: Mapped[str] = mapped_column(
        ForeignKey("agent_versions.id", ondelete="CASCADE"), index=True
    )
    triggered_by_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("demo_sessions.id", ondelete="SET NULL"), nullable=True
    )
    state: Mapped[str] = mapped_column(String(16), index=True)
    suite_version: Mapped[str] = mapped_column(String(48))
    online_model: Mapped[str] = mapped_column(String(100))
    judge_model: Mapped[str] = mapped_column(String(100))
    embedding_model: Mapped[str] = mapped_column(String(100))
    moderation_model: Mapped[str] = mapped_column(String(100))
    total_cases: Mapped[int] = mapped_column(Integer)
    completed_cases: Mapped[int] = mapped_column(Integer, default=0)
    passed_cases: Mapped[int] = mapped_column(Integer, default=0)
    failed_cases: Mapped[int] = mapped_column(Integer, default=0)
    error_cases: Mapped[int] = mapped_column(Integer, default=0)
    grounded_pass_rate: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    age_average: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True)
    instruction_average: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True)
    release_eligible: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Numeric(12, 8), default=0)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    timeout_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EvaluationCaseResult(Base):
    __tablename__ = "evaluation_case_results"
    __table_args__ = (UniqueConstraint("evaluation_run_id", "evaluation_case_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    evaluation_run_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"), index=True
    )
    evaluation_case_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_cases.id", ondelete="RESTRICT"), index=True
    )
    state: Mapped[str] = mapped_column(String(16))
    passed: Mapped[int] = mapped_column(Integer, default=0)
    blocking: Mapped[int] = mapped_column(Integer, default=0)
    runtime_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("chat_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    deterministic_checks_json: Mapped[str] = mapped_column(Text)
    evidence_json: Mapped[str] = mapped_column(Text)
    evidence_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    age_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    instruction_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    judge_rationale: Mapped[str | None] = mapped_column(String(500), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Numeric(12, 8), default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    safe_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
