"""Add persisted Teacher reviews for immutable version decisions.

Revision ID: 0006_versions_review
Revises: 0005_evaluation
Create Date: 2026-08-06
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_versions_review"
down_revision: str | None = "0005_evaluation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "teacher_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("version_id", sa.String(36), nullable=False),
        sa.Column("evaluation_run_id", sa.String(36), nullable=False),
        sa.Column("session_id", sa.String(36), nullable=True),
        sa.Column("decision", sa.String(24), nullable=False),
        sa.Column("feedback", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["version_id"], ["agent_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evaluation_run_id"], ["evaluation_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["session_id"], ["demo_sessions.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_teacher_reviews_version_id", "teacher_reviews", ["version_id"])


def downgrade() -> None:
    op.drop_table("teacher_reviews")
