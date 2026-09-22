"""Add immutable dependency, milestone, constraint, and calendar proposals."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020_schedule_logic"
down_revision: str | None = "0019_schedule_draft_generation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "schedule_logic_proposal",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(), nullable=False),
        sa.Column("project_id", postgresql.UUID(), nullable=False),
        sa.Column("generation_id", postgresql.UUID(), nullable=False),
        sa.Column("logic_version", sa.String(40), nullable=False),
        sa.Column("dependencies", jsonb, nullable=False),
        sa.Column("milestones", jsonb, nullable=False),
        sa.Column("constraints", jsonb, nullable=False),
        sa.Column("calendar", jsonb, nullable=False),
        sa.Column("sequence_templates", jsonb, nullable=False),
        sa.Column("assumptions", jsonb, nullable=False),
        sa.Column("warnings", jsonb, nullable=False),
        sa.Column("review_state", sa.String(30), nullable=False),
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
        sa.UniqueConstraint("generation_id", name="uq_schedule_logic_generation"),
        sa.UniqueConstraint("project_id", "idempotency_key", name="uq_schedule_logic_idempotency"),
    )
    for column in ("organization_id", "project_id", "generation_id"):
        op.create_index(f"ix_schedule_logic_proposal_{column}", "schedule_logic_proposal", [column])
    op.execute("""
        CREATE TRIGGER schedule_logic_proposal_append_only
        BEFORE UPDATE OR DELETE ON schedule_logic_proposal
        FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER schedule_logic_proposal_append_only ON schedule_logic_proposal")
    op.drop_table("schedule_logic_proposal")
