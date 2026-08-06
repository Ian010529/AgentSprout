"""Add explicit reset protection for the fixed public sample.

Revision ID: 0007_publish
Revises: 0006_versions_review
Create Date: 2026-08-06
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_publish"
down_revision: str | None = "0006_versions_review"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column("is_fixed_sample", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("agents", "is_fixed_sample")
