"""Add immutable weighted project-control snapshots."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0024_project_control_snapshots"
down_revision: str | None = "0023_bootstrap_revision_delta"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.drop_constraint("ck_context_type", "authorized_context_version", type_="check")
    op.create_check_constraint(
        "ck_context_type",
        "authorized_context_version",
        "context_type IN ('SCHEDULE', 'BUDGET', 'BOQ', 'PROGRESS_WEIGHTING')",
    )
    op.create_table(
        "project_control_snapshot",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(), nullable=False),
        sa.Column("project_id", postgresql.UUID(), nullable=False),
        sa.Column("snapshot_number", sa.Integer(), nullable=False),
        sa.Column("data_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("progress_weighting_context_id", postgresql.UUID(), nullable=False),
        sa.Column("schedule_context_id", postgresql.UUID(), nullable=False),
        sa.Column("weighting_basis", sa.String(40), nullable=False),
        sa.Column("measurement_basis", sa.String(80), nullable=False),
        sa.Column("package_results", jsonb, nullable=False),
        sa.Column("package_exclusions", jsonb, nullable=False),
        sa.Column("cost_assessment_refs", jsonb, nullable=False),
        sa.Column("forecast_projection_refs", jsonb, nullable=False),
        sa.Column("policy_versions", jsonb, nullable=False),
        sa.Column("planned_ratio", sa.Numeric(12, 8), nullable=False),
        sa.Column("actual_ratio", sa.Numeric(12, 8), nullable=False),
        sa.Column("variance_ratio", sa.Numeric(12, 8), nullable=False),
        sa.Column("progress_status", sa.String(20), nullable=False),
        sa.Column("progress_policy_version", sa.String(40), nullable=False),
        sa.Column("input_evidence_ids", jsonb, nullable=False),
        sa.Column("truth_type", sa.String(30), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("limitations", jsonb, nullable=False),
        sa.Column("formula_version", sa.String(40), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("snapshot_number > 0", name="ck_project_control_snapshot_no"),
        sa.CheckConstraint(
            "planned_ratio >= 0 AND planned_ratio <= 1",
            name="ck_project_control_planned_ratio",
        ),
        sa.CheckConstraint(
            "actual_ratio >= 0 AND actual_ratio <= 1",
            name="ck_project_control_actual_ratio",
        ),
        sa.CheckConstraint(
            "progress_status IN ('AHEAD', 'ON_PLAN', 'BEHIND')",
            name="ck_project_control_progress_status",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_project_control_confidence"
        ),
        sa.CheckConstraint("truth_type = 'DERIVED_METRIC'", name="ck_project_control_truth_type"),
        sa.CheckConstraint(
            "request_hash ~ '^[0-9a-f]{64}$'", name="ck_project_control_request_hash"
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["progress_weighting_context_id"],
            ["authorized_context_version.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["schedule_context_id"], ["authorized_context_version.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("project_id", "snapshot_number", name="uq_project_control_snapshot_no"),
        sa.UniqueConstraint(
            "project_id", "idempotency_key", name="uq_project_control_snapshot_idem"
        ),
    )
    for column in (
        "organization_id",
        "project_id",
        "progress_weighting_context_id",
        "schedule_context_id",
    ):
        op.create_index(
            f"ix_project_control_snapshot_{column}", "project_control_snapshot", [column]
        )
    op.execute("""
        CREATE TRIGGER project_control_snapshot_append_only
        BEFORE UPDATE OR DELETE ON project_control_snapshot
        FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER project_control_snapshot_append_only ON project_control_snapshot")
    op.drop_table("project_control_snapshot")
    # Retain the widened context constraint: authorized weighting versions are governed history
    # and must not be deleted merely to permit a schema rollback.
