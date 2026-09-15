"""Add immutable outcome-linked learning and calibration records."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015_learning_records"
down_revision: str | None = "0014_response_lifecycle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "case_learning_record",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(),
            sa.ForeignKey("organization.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(),
            sa.ForeignKey("project.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "case_id",
            postgresql.UUID(),
            sa.ForeignKey("decision_case.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "response_outcome_id",
            postgresql.UUID(),
            sa.ForeignKey("response_outcome.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "human_decision_id",
            postgresql.UUID(),
            sa.ForeignKey("human_decision.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "orchestration_run_id",
            postgresql.UUID(),
            sa.ForeignKey("orchestration_run.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("finding", sa.Text(), nullable=False),
        sa.Column("contributing_factors", postgresql.JSONB(), nullable=False),
        sa.Column("calibration", postgresql.JSONB(), nullable=False),
        sa.Column("calibration_notes", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("recorded_by", sa.String(200), nullable=False),
        sa.Column(
            "recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("case_id", "idempotency_key", name="uq_case_learning_idempotency"),
    )
    for column in (
        "organization_id",
        "project_id",
        "case_id",
        "response_outcome_id",
        "human_decision_id",
        "orchestration_run_id",
    ):
        op.create_index(f"ix_case_learning_record_{column}", "case_learning_record", [column])
    op.execute("""
        CREATE TRIGGER case_learning_record_append_only
        BEFORE UPDATE OR DELETE ON case_learning_record
        FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER case_learning_record_append_only ON case_learning_record")
    op.drop_table("case_learning_record")
