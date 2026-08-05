from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
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
