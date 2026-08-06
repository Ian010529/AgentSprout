"""Add knowledge documents and persisted ingestion jobs.

Revision ID: 0003_knowledge
Revises: 0002_access_dashboard
Create Date: 2026-08-06
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_knowledge"
down_revision: str | None = "0002_access_dashboard"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("version_id", sa.String(36), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("media_type", sa.String(80), nullable=False),
        sa.Column("extension", sa.String(8), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("storage_path", sa.String(500), nullable=False, unique=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=True),
        sa.Column("embedding_model", sa.String(100), nullable=False),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("is_active", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["version_id"], ["agent_versions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("version_id", "sha256", name="uq_knowledge_version_sha256"),
        sa.CheckConstraint("extension IN ('pdf','txt','md')", name="ck_knowledge_extension"),
        sa.CheckConstraint(
            "status IN ('UPLOADED','EXTRACTING','CHUNKING','EMBEDDING','READY','FAILED','RETIRED')",
            name="ck_knowledge_status",
        ),
        sa.CheckConstraint("is_active IN (0,1)", name="ck_knowledge_active"),
    )
    op.create_index("ix_knowledge_documents_version_id", "knowledge_documents", ["version_id"])
    op.create_index("ix_knowledge_documents_status", "knowledge_documents", ["status"])
    op.create_index("ix_knowledge_version_status", "knowledge_documents", ["version_id", "status"])

    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("progress_completed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("safe_error_message", sa.String(240), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("document_id", "attempt"),
        sa.CheckConstraint(
            "state IN ('UPLOADED','EXTRACTING','CHUNKING','EMBEDDING','READY','FAILED')",
            name="ck_ingestion_state",
        ),
    )
    op.create_index("ix_ingestion_jobs_document_id", "ingestion_jobs", ["document_id"])
    op.create_index("ix_ingestion_jobs_state", "ingestion_jobs", ["state"])


def downgrade() -> None:
    op.drop_table("ingestion_jobs")
    op.drop_table("knowledge_documents")
