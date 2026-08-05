"""Establish the migration baseline without future-module domain tables.

Revision ID: 0001_foundation
Revises:
Create Date: 2026-08-06
"""

from collections.abc import Sequence

revision: str = "0001_foundation"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
