"""Add immutable proposed WBS and work-package structure versions."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018_boq_planning_structure"
down_revision: str | None = "0017_boq_normalization"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "boq_planning_structure_version",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(), nullable=False),
        sa.Column("project_id", postgresql.UUID(), nullable=False),
        sa.Column("normalization_run_id", postgresql.UUID(), nullable=False),
        sa.Column("supersedes_version_id", postgresql.UUID(), nullable=True),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("wbs_nodes", jsonb, nullable=False),
        sa.Column("work_packages", jsonb, nullable=False),
        sa.Column("line_mappings", jsonb, nullable=False),
        sa.Column("unmapped_lines", jsonb, nullable=False),
        sa.Column("assumptions", jsonb, nullable=False),
        sa.Column("warnings", jsonb, nullable=False),
        sa.Column("change_summary", jsonb, nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["normalization_run_id"], ["boq_normalization_run.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_version_id"],
            ["boq_planning_structure_version.id"],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("version_number > 0", name="ck_boq_structure_version_positive"),
        sa.CheckConstraint(
            "status IN ('PROPOSED','REVIEWED','REJECTED')", name="ck_boq_structure_status"
        ),
        sa.CheckConstraint(
            "action IN ('GENERATE','SPLIT_PACKAGE','MERGE_PACKAGES','REMAP_LINE',"
            "'ACCEPT_PROPOSAL','REJECT_PROPOSAL')",
            name="ck_boq_structure_action",
        ),
        sa.UniqueConstraint(
            "normalization_run_id", "version_number", name="uq_boq_structure_version"
        ),
        sa.UniqueConstraint("project_id", "idempotency_key", name="uq_boq_structure_idempotency"),
    )
    for column in (
        "organization_id",
        "project_id",
        "normalization_run_id",
        "supersedes_version_id",
    ):
        op.create_index(
            f"ix_boq_planning_structure_version_{column}",
            "boq_planning_structure_version",
            [column],
        )
    op.execute("""
        CREATE TRIGGER boq_planning_structure_version_append_only
        BEFORE UPDATE OR DELETE ON boq_planning_structure_version
        FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
    """)


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER boq_planning_structure_version_append_only ON boq_planning_structure_version"
    )
    op.drop_table("boq_planning_structure_version")
