"""Add Studio conversations, safe chat runs, citations, and traces.

Revision ID: 0004_playground
Revises: 0003_knowledge
Create Date: 2026-08-06
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_playground"
down_revision: str | None = "0003_knowledge"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "studio_conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("version_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["version_id"], ["agent_versions.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_studio_conversations_version_id", "studio_conversations", ["version_id"])
    op.create_index("ix_studio_conversations_expires_at", "studio_conversations", ["expires_at"])

    op.create_table(
        "chat_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("version_id", sa.String(36), nullable=False),
        sa.Column("conversation_id", sa.String(36), nullable=True),
        sa.Column("surface", sa.String(16), nullable=False),
        sa.Column("phase", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("result_type", sa.String(16), nullable=True),
        sa.Column("input_message_id", sa.String(36), nullable=True),
        sa.Column("output_message_id", sa.String(36), nullable=True),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("online_model", sa.String(100), nullable=False),
        sa.Column("moderation_model", sa.String(100), nullable=False),
        sa.Column("embedding_model", sa.String(100), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reasoning_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost_usd", sa.Numeric(12, 8), nullable=False, server_default="0"),
        sa.Column("retrieval_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provider_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("safe_error_message", sa.String(240), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["version_id"], ["agent_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["studio_conversations.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint("surface IN ('STUDIO','PUBLIC','EVALUATION')", name="ck_chat_surface"),
        sa.CheckConstraint("status IN ('RUNNING','COMPLETED','FAILED')", name="ck_chat_status"),
    )
    op.create_index("ix_chat_runs_version_id", "chat_runs", ["version_id"])
    op.create_index("ix_chat_runs_conversation_id", "chat_runs", ["conversation_id"])
    op.create_index("ix_chat_runs_phase", "chat_runs", ["phase"])
    op.create_index("ix_chat_runs_status", "chat_runs", ["status"])
    op.create_index("ix_chat_runs_expires_at", "chat_runs", ["expires_at"])

    op.create_table(
        "messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("conversation_id", sa.String(36), nullable=False),
        sa.Column("run_id", sa.String(36), nullable=True),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["studio_conversations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["run_id"], ["chat_runs.id"], ondelete="CASCADE"),
        sa.CheckConstraint("role IN ('USER','ASSISTANT')", name="ck_message_role"),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("ix_messages_run_id", "messages", ["run_id"])

    op.create_table(
        "message_citations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("message_id", sa.String(36), nullable=False),
        sa.Column("chunk_id", sa.String(160), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("message_id", "chunk_id"),
    )
    op.create_index("ix_message_citations_message_id", "message_citations", ["message_id"])

    op.create_table(
        "run_node_traces",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("node_name", sa.String(48), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("safe_summary_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["chat_runs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("run_id", "sequence"),
    )
    op.create_index("ix_run_node_traces_run_id", "run_node_traces", ["run_id"])

    op.create_table(
        "safety_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("version_id", sa.String(36), nullable=False),
        sa.Column("category", sa.String(48), nullable=False),
        sa.Column("action", sa.String(48), nullable=False),
        sa.Column("detector", sa.String(48), nullable=False),
        sa.Column("safe_summary", sa.String(240), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["chat_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["version_id"], ["agent_versions.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_safety_events_run_id", "safety_events", ["run_id"])
    op.create_index("ix_safety_events_version_id", "safety_events", ["version_id"])


def downgrade() -> None:
    op.drop_table("safety_events")
    op.drop_table("run_node_traces")
    op.drop_table("message_citations")
    op.drop_table("messages")
    op.drop_table("chat_runs")
    op.drop_table("studio_conversations")
