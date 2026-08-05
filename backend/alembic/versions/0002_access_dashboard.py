"""Add Studio access, Agent, Draft, audit, limiter, and idempotency state.

Revision ID: 0002_access_dashboard
Revises: 0001_foundation
Create Date: 2026-08-06
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_access_dashboard"
down_revision: str | None = "0001_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "demo_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("csrf_hash", sa.String(64), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("role IN ('STUDENT','TEACHER')", name="ck_demo_sessions_role"),
    )
    op.create_index("ix_demo_sessions_token_hash", "demo_sessions", ["token_hash"])
    op.create_index("ix_demo_sessions_expires_at", "demo_sessions", ["expires_at"])

    op.create_table(
        "agents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("slug", sa.String(120), nullable=False, unique=True),
        sa.Column("display_name", sa.String(80), nullable=False),
        sa.Column("current_draft_version_id", sa.String(36), nullable=True),
        sa.Column("published_version_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agents_slug", "agents", ["slug"])

    op.create_table(
        "agent_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("agent_id", sa.String(36), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("project_name", sa.String(80), nullable=False),
        sa.Column("problem_to_solve", sa.String(500), nullable=False),
        sa.Column("intended_users", sa.String(240), nullable=False),
        sa.Column("audience_age", sa.String(16), nullable=False),
        sa.Column("success_goal", sa.String(300), nullable=False),
        sa.Column("welcome_message", sa.String(240), nullable=False),
        sa.Column("tone", sa.String(16), nullable=False),
        sa.Column("response_length", sa.String(16), nullable=False),
        sa.Column("custom_instructions", sa.String(500), nullable=False),
        sa.Column("what_changed", sa.String(500), nullable=True),
        sa.Column("why_changed", sa.String(500), nullable=True),
        sa.Column("source_version_id", sa.String(36), nullable=True),
        sa.Column("active_document_id", sa.String(36), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("agent_id", "version_number"),
        sa.CheckConstraint(
            "state IN ('DRAFT','IN_REVIEW','CHANGES_REQUESTED','APPROVED','PUBLISHED','WITHDRAWN')",
            name="ck_agent_versions_state",
        ),
        sa.CheckConstraint(
            "audience_age IN ('AGE_7_11','AGE_12_17')", name="ck_agent_versions_audience"
        ),
        sa.CheckConstraint(
            "tone IN ('FRIENDLY','CURIOUS','COACH_LIKE')", name="ck_agent_versions_tone"
        ),
        sa.CheckConstraint(
            "response_length IN ('SHORT','BALANCED')", name="ck_agent_versions_length"
        ),
    )
    op.create_index("ix_agent_versions_agent_id", "agent_versions", ["agent_id"])
    op.create_index("ix_agent_versions_state", "agent_versions", ["state"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), nullable=True),
        sa.Column("actor_type", sa.String(32), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(32), nullable=True),
        sa.Column("target_id", sa.String(36), nullable=True),
        sa.Column("result", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["demo_sessions.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_audit_events_session_id", "audit_events", ["session_id"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"])

    op.create_table(
        "rate_limit_buckets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("subject_hash", sa.String(64), nullable=False),
        sa.Column("scope", sa.String(32), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.UniqueConstraint("subject_hash", "scope", "window_start"),
    )
    op.create_index(
        "ix_rate_limit_lookup",
        "rate_limit_buckets",
        ["subject_hash", "scope", "window_end"],
    )

    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("scope", sa.String(48), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["demo_sessions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("session_id", "scope", "key_hash"),
    )
    op.create_index("ix_idempotency_session", "idempotency_records", ["session_id"])
    op.create_index("ix_idempotency_expires_at", "idempotency_records", ["expires_at"])


def downgrade() -> None:
    op.drop_table("idempotency_records")
    op.drop_table("rate_limit_buckets")
    op.drop_table("audit_events")
    op.drop_table("agent_versions")
    op.drop_table("agents")
    op.drop_table("demo_sessions")
