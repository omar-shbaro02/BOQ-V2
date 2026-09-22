"""Add deterministic bootstrap CPM calculations."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021_bootstrap_cpm"
down_revision: str | None = "0020_schedule_logic"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "bootstrap_schedule_calculation",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(), nullable=False),
        sa.Column("project_id", postgresql.UUID(), nullable=False),
        sa.Column("generation_id", postgresql.UUID(), nullable=False),
        sa.Column("logic_proposal_id", postgresql.UUID(), nullable=False),
        sa.Column("calculation_version", sa.String(40), nullable=False),
        sa.Column("project_start", sa.Date(), nullable=False),
        sa.Column("proposed_finish", sa.Date()),
        sa.Column("readiness", sa.String(40), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("activity_results", jsonb, nullable=False),
        sa.Column("milestone_results", jsonb, nullable=False),
        sa.Column("validation_findings", jsonb, nullable=False),
        sa.Column("critical_activity_ids", jsonb, nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["generation_id"], ["schedule_draft_generation.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["logic_proposal_id"], ["schedule_logic_proposal.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("logic_proposal_id", name="uq_bootstrap_calculation_logic"),
        sa.UniqueConstraint("project_id", "idempotency_key", name="uq_bootstrap_calculation_idem"),
    )
    for column in ("organization_id", "project_id", "generation_id", "logic_proposal_id"):
        op.create_index(
            f"ix_bootstrap_schedule_calculation_{column}",
            "bootstrap_schedule_calculation",
            [column],
        )
    op.execute("""
        CREATE TRIGGER bootstrap_schedule_calculation_append_only
        BEFORE UPDATE OR DELETE ON bootstrap_schedule_calculation
        FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
    """)


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER bootstrap_schedule_calculation_append_only ON bootstrap_schedule_calculation"
    )
    op.drop_table("bootstrap_schedule_calculation")
