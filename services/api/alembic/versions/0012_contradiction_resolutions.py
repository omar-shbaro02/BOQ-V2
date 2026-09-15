"""Add immutable reviewed specialist contradiction resolutions."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_contradiction_resolutions"
down_revision: str | None = "0011_orchestration_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "specialist_contradiction_resolution",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(), nullable=False),
        sa.Column("project_id", postgresql.UUID(), nullable=False),
        sa.Column("case_id", postgresql.UUID(), nullable=False),
        sa.Column("snapshot_id", postgresql.UUID(), nullable=False),
        sa.Column("orchestration_run_id", postgresql.UUID(), nullable=False),
        sa.Column("contradiction_index", sa.Integer(), nullable=False),
        sa.Column("contradiction_type", sa.String(40), nullable=False),
        sa.Column("source_result_ids", jsonb, nullable=False),
        sa.Column("selected_result_id", sa.String(80), nullable=False),
        sa.Column("rejected_result_ids", jsonb, nullable=False),
        sa.Column("resolution_basis", sa.Text(), nullable=False),
        sa.Column("downstream_invalidations", jsonb, nullable=False),
        sa.Column("resolved_by", sa.String(200), nullable=False),
        sa.Column(
            "resolved_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["case_id"], ["decision_case.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["case_snapshot.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["orchestration_run_id"], ["orchestration_run.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "orchestration_run_id",
            "contradiction_index",
            name="uq_specialist_contradiction_resolution",
        ),
        sa.CheckConstraint("contradiction_index >= 0", name="ck_specialist_contradiction_index"),
    )
    for column in (
        "organization_id",
        "project_id",
        "case_id",
        "snapshot_id",
        "orchestration_run_id",
    ):
        op.create_index(
            f"ix_specialist_contradiction_resolution_{column}",
            "specialist_contradiction_resolution",
            [column],
        )
    op.execute("""
        CREATE TRIGGER specialist_contradiction_resolution_append_only
          BEFORE UPDATE OR DELETE ON specialist_contradiction_resolution
          FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
    """)


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER specialist_contradiction_resolution_append_only "
        "ON specialist_contradiction_resolution"
    )
    op.drop_table("specialist_contradiction_resolution")
