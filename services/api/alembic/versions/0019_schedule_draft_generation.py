"""Add immutable activity, duration, productivity, and assumption drafts."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019_schedule_draft_generation"
down_revision: str | None = "0018_boq_planning_structure"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "schedule_draft_generation",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(), nullable=False),
        sa.Column("project_id", postgresql.UUID(), nullable=False),
        sa.Column("planning_structure_id", postgresql.UUID(), nullable=False),
        sa.Column("generator_version", sa.String(40), nullable=False),
        sa.Column("draft_state", sa.String(40), nullable=False),
        sa.Column("productivity_inputs", jsonb, nullable=False),
        sa.Column("duration_inputs", jsonb, nullable=False),
        sa.Column("warnings", jsonb, nullable=False),
        sa.Column("activity_count", sa.Integer(), nullable=False),
        sa.Column("unresolved_duration_count", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["planning_structure_id"], ["boq_planning_structure_version.id"], ondelete="RESTRICT"
        ),
        sa.CheckConstraint("activity_count >= 0", name="ck_schedule_draft_activity_count"),
        sa.CheckConstraint(
            "unresolved_duration_count >= 0", name="ck_schedule_draft_unresolved_count"
        ),
        sa.UniqueConstraint("planning_structure_id", name="uq_schedule_generation_structure"),
        sa.UniqueConstraint(
            "project_id", "idempotency_key", name="uq_schedule_generation_idempotency"
        ),
    )
    for column in ("organization_id", "project_id", "planning_structure_id"):
        op.create_index(
            f"ix_schedule_draft_generation_{column}", "schedule_draft_generation", [column]
        )

    op.create_table(
        "proposed_schedule_activity",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(), nullable=False),
        sa.Column("project_id", postgresql.UUID(), nullable=False),
        sa.Column("generation_id", postgresql.UUID(), nullable=False),
        sa.Column("activity_code", sa.String(80), nullable=False),
        sa.Column("wbs_node_id", sa.String(80), nullable=False),
        sa.Column("work_package_id", sa.String(80), nullable=False),
        sa.Column("boq_line_refs", jsonb, nullable=False),
        sa.Column("activity_name", sa.String(300), nullable=False),
        sa.Column("activity_type", sa.String(40), nullable=False),
        sa.Column("trade", sa.String(160), nullable=True),
        sa.Column("location", sa.String(240), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 6), nullable=True),
        sa.Column("unit", sa.String(80), nullable=True),
        sa.Column("duration_working_days", sa.Numeric(18, 6), nullable=True),
        sa.Column("duration_unrounded", sa.Numeric(24, 10), nullable=True),
        sa.Column("duration_status", sa.String(40), nullable=False),
        sa.Column("duration_basis", sa.String(50), nullable=False),
        sa.Column("productivity", jsonb, nullable=True),
        sa.Column("calendar_id", sa.String(80), nullable=True),
        sa.Column("responsible_role", sa.String(160), nullable=True),
        sa.Column("confidence", sa.String(20), nullable=False),
        sa.Column("review_state", sa.String(30), nullable=False),
        sa.Column("warnings", jsonb, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["generation_id"], ["schedule_draft_generation.id"], ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "duration_working_days IS NULL OR duration_working_days > 0",
            name="ck_proposed_activity_duration",
        ),
        sa.UniqueConstraint("generation_id", "activity_code", name="uq_proposed_activity_code"),
    )
    for column in ("organization_id", "project_id", "generation_id"):
        op.create_index(
            f"ix_proposed_schedule_activity_{column}", "proposed_schedule_activity", [column]
        )

    op.create_table(
        "planning_assumption",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(), nullable=False),
        sa.Column("project_id", postgresql.UUID(), nullable=False),
        sa.Column("generation_id", postgresql.UUID(), nullable=False),
        sa.Column("proposition", sa.Text(), nullable=False),
        sa.Column("reason_needed", sa.Text(), nullable=False),
        sa.Column("affected_activity_ids", jsonb, nullable=False),
        sa.Column("source_basis", sa.String(200), nullable=False),
        sa.Column("confidence", sa.String(20), nullable=False),
        sa.Column("consequence_if_wrong", sa.Text(), nullable=False),
        sa.Column("validation_owner", sa.String(200), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["generation_id"], ["schedule_draft_generation.id"], ondelete="RESTRICT"
        ),
    )
    for column in ("organization_id", "project_id", "generation_id"):
        op.create_index(f"ix_planning_assumption_{column}", "planning_assumption", [column])

    for table in ("schedule_draft_generation", "proposed_schedule_activity", "planning_assumption"):
        op.execute(f"""
            CREATE TRIGGER {table}_append_only
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
        """)


def downgrade() -> None:
    for table in ("planning_assumption", "proposed_schedule_activity", "schedule_draft_generation"):
        op.execute(f"DROP TRIGGER {table}_append_only ON {table}")
        op.drop_table(table)
