"""Add immutable evaluation suite, runs, and case evidence.

Revision ID: 0005_evaluation
Revises: 0004_playground
Create Date: 2026-08-06
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_evaluation"
down_revision: str | None = "0004_playground"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("chat_runs", sa.Column("audience_age_override", sa.String(16), nullable=True))
    op.create_table(
        "evaluation_cases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_key", sa.String(24), nullable=False, unique=True),
        sa.Column("suite_version", sa.String(48), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("prompt_template", sa.Text(), nullable=False),
        sa.Column("audience_age", sa.String(16), nullable=False),
        sa.Column("expected_result_type", sa.String(16), nullable=False),
        sa.Column("expected_pages_json", sa.Text(), nullable=False),
        sa.Column("rubric_version", sa.String(48), nullable=False),
        sa.Column("enabled", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index("ix_evaluation_cases_case_key", "evaluation_cases", ["case_key"])
    op.create_index("ix_evaluation_cases_suite_version", "evaluation_cases", ["suite_version"])
    op.create_index("ix_evaluation_cases_category", "evaluation_cases", ["category"])
    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("version_id", sa.String(36), nullable=False),
        sa.Column("triggered_by_session_id", sa.String(36), nullable=True),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("suite_version", sa.String(48), nullable=False),
        sa.Column("online_model", sa.String(100), nullable=False),
        sa.Column("judge_model", sa.String(100), nullable=False),
        sa.Column("embedding_model", sa.String(100), nullable=False),
        sa.Column("moderation_model", sa.String(100), nullable=False),
        sa.Column("total_cases", sa.Integer(), nullable=False),
        sa.Column("completed_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("passed_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("grounded_pass_rate", sa.Numeric(6, 4), nullable=True),
        sa.Column("age_average", sa.Numeric(4, 2), nullable=True),
        sa.Column("instruction_average", sa.Numeric(4, 2), nullable=True),
        sa.Column("release_eligible", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost_usd", sa.Numeric(12, 8), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("timeout_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["version_id"], ["agent_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["triggered_by_session_id"], ["demo_sessions.id"], ondelete="SET NULL"
        ),
    )
    op.create_index("ix_evaluation_runs_version_id", "evaluation_runs", ["version_id"])
    op.create_index("ix_evaluation_runs_state", "evaluation_runs", ["state"])
    op.create_table(
        "evaluation_case_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("evaluation_run_id", sa.String(36), nullable=False),
        sa.Column("evaluation_case_id", sa.String(36), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("passed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("blocking", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("runtime_run_id", sa.String(36), nullable=True),
        sa.Column("deterministic_checks_json", sa.Text(), nullable=False),
        sa.Column("evidence_json", sa.Text(), nullable=False),
        sa.Column("evidence_score", sa.Integer(), nullable=True),
        sa.Column("age_score", sa.Integer(), nullable=True),
        sa.Column("instruction_score", sa.Integer(), nullable=True),
        sa.Column("judge_rationale", sa.String(500), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost_usd", sa.Numeric(12, 8), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("safe_error_code", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["evaluation_run_id"], ["evaluation_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["evaluation_case_id"], ["evaluation_cases.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["runtime_run_id"], ["chat_runs.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("evaluation_run_id", "evaluation_case_id"),
    )
    op.create_index(
        "ix_evaluation_case_results_evaluation_run_id",
        "evaluation_case_results",
        ["evaluation_run_id"],
    )
    op.create_index(
        "ix_evaluation_case_results_evaluation_case_id",
        "evaluation_case_results",
        ["evaluation_case_id"],
    )
    op.create_index(
        "ix_evaluation_case_results_runtime_run_id", "evaluation_case_results", ["runtime_run_id"]
    )


def downgrade() -> None:
    op.drop_table("evaluation_case_results")
    op.drop_table("evaluation_runs")
    op.drop_table("evaluation_cases")
    op.drop_column("chat_runs", "audience_age_override")
