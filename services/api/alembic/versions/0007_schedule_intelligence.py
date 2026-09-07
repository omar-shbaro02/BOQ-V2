"""Add schedule network and dependency intelligence."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_schedule_intelligence"
down_revision: str | None = "0006_progress_intelligence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def uid(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, postgresql.UUID(as_uuid=True), nullable=nullable)


def scope() -> tuple[sa.Column, sa.Column]:
    return uid("organization_id"), uid("project_id")


def scope_fks() -> tuple[sa.ForeignKeyConstraint, sa.ForeignKeyConstraint]:
    return (
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="RESTRICT"),
    )


def timestamp(name: str) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def indexes(table: str) -> None:
    op.create_index(f"ix_{table}_organization_id", table, ["organization_id"])
    op.create_index(f"ix_{table}_project_id", table, ["project_id"])


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.add_column(
        "decision_case",
        sa.Column("last_schedule_assessment_id", postgresql.UUID(), nullable=True),
    )
    op.create_table(
        "schedule_analysis_policy",
        uid("id"),
        *scope(),
        sa.Column("policy_version", sa.String(40), nullable=False),
        sa.Column("on_time_tolerance_days", sa.Numeric(8, 3), nullable=False),
        sa.Column("maximum_schedule_age_days", sa.Integer(), nullable=False),
        sa.Column("require_dependency_for_consequence", sa.Boolean(), nullable=False),
        sa.Column("allow_calculated_float", sa.Boolean(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        uid("supersedes_policy_id", True),
        sa.Column("created_by", sa.String(200), nullable=False),
        timestamp("created_at"),
        sa.CheckConstraint(
            "on_time_tolerance_days >= 0 AND on_time_tolerance_days <= 30",
            name="ck_schedule_policy_tolerance",
        ),
        sa.CheckConstraint("maximum_schedule_age_days >= 1", name="ck_schedule_policy_maximum_age"),
        *scope_fks(),
        sa.ForeignKeyConstraint(
            ["supersedes_policy_id"], ["schedule_analysis_policy.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "policy_version", name="uq_schedule_policy_version"),
    )
    indexes("schedule_analysis_policy")

    op.create_table(
        "schedule_assessment",
        uid("id"),
        *scope(),
        uid("case_id"),
        uid("snapshot_id"),
        uid("schedule_context_id"),
        uid("controlled_object_id"),
        uid("delay_evidence_item_id"),
        sa.Column("assessment_number", sa.Integer(), nullable=False),
        sa.Column("activity_code", sa.String(80), nullable=False),
        sa.Column("data_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("planned_start", sa.Date(), nullable=False),
        sa.Column("planned_finish", sa.Date(), nullable=False),
        sa.Column("delay_days", sa.Numeric(12, 3), nullable=False),
        sa.Column("timing_direction", sa.String(20), nullable=False),
        sa.Column("effective_float_days", sa.Numeric(12, 3), nullable=True),
        sa.Column("float_source", sa.String(20), nullable=False),
        sa.Column("schedule_quality", sa.String(40), nullable=False),
        sa.Column("assessment_status", sa.String(40), nullable=False),
        sa.Column("exposure_level", sa.String(30), nullable=False),
        sa.Column("downstream_paths", jsonb, nullable=False),
        sa.Column("affected_activity_codes", jsonb, nullable=False),
        sa.Column("milestone_exposures", jsonb, nullable=False),
        sa.Column("project_completion_exposure_days", sa.Numeric(12, 3), nullable=True),
        sa.Column("maximum_supported_conclusion", sa.String(40), nullable=False),
        sa.Column("input_evidence_ids", jsonb, nullable=False),
        sa.Column("truth_type", sa.String(30), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("limitations", jsonb, nullable=False),
        sa.Column("policy_version", sa.String(40), nullable=False),
        sa.Column("formula_version", sa.String(40), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("assessed_by", sa.String(200), nullable=False),
        timestamp("assessed_at"),
        sa.CheckConstraint("assessment_number > 0", name="ck_schedule_assessment_number"),
        sa.CheckConstraint(
            "timing_direction IN ('AHEAD','ON_TIME','DELAYED')",
            name="ck_schedule_timing_direction",
        ),
        sa.CheckConstraint(
            "float_source IN ('SUPPLIED','CALCULATED','UNAVAILABLE')",
            name="ck_schedule_float_source",
        ),
        sa.CheckConstraint(
            "schedule_quality IN ('VALID','VALID_WITH_LIMITATIONS')",
            name="ck_schedule_quality",
        ),
        sa.CheckConstraint(
            "assessment_status IN ('ASSESSED','VERIFICATION_REQUIRED','INSUFFICIENT')",
            name="ck_schedule_assessment_status",
        ),
        sa.CheckConstraint(
            "exposure_level IN ('LOCAL','DOWNSTREAM','MILESTONE','PROJECT_COMPLETION')",
            name="ck_schedule_exposure_level",
        ),
        sa.CheckConstraint(
            "maximum_supported_conclusion IN ('LOCAL_TIMING_VARIANCE',"
            "'DOWNSTREAM_EXPOSURE','MILESTONE_EXPOSURE')",
            name="ck_schedule_conclusion",
        ),
        sa.CheckConstraint(
            "truth_type IN ('DERIVED_METRIC','CONTRADICTED')",
            name="ck_schedule_output_truth",
        ),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_schedule_confidence"),
        sa.CheckConstraint("request_hash ~ '^[0-9a-f]{64}$'", name="ck_schedule_request_hash"),
        *scope_fks(),
        sa.ForeignKeyConstraint(["case_id"], ["decision_case.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["case_snapshot.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["schedule_context_id"], ["authorized_context_version.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["controlled_object_id"], ["controlled_object.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["delay_evidence_item_id"], ["evidence_item.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "assessment_number", name="uq_schedule_assessment_number"),
        sa.UniqueConstraint(
            "case_id", "idempotency_key", name="uq_schedule_assessment_idempotency"
        ),
    )
    indexes("schedule_assessment")
    for column in (
        "case_id",
        "snapshot_id",
        "schedule_context_id",
        "controlled_object_id",
    ):
        op.create_index(f"ix_schedule_assessment_{column}", "schedule_assessment", [column])
    op.create_foreign_key(
        "fk_decision_case_last_schedule_assessment",
        "decision_case",
        "schedule_assessment",
        ["last_schedule_assessment_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.execute(
        """
        CREATE TRIGGER schedule_analysis_policy_append_only
          BEFORE UPDATE OR DELETE ON schedule_analysis_policy
          FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
        CREATE TRIGGER schedule_assessment_append_only
          BEFORE UPDATE OR DELETE ON schedule_assessment
          FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER schedule_assessment_append_only ON schedule_assessment")
    op.execute("DROP TRIGGER schedule_analysis_policy_append_only ON schedule_analysis_policy")
    op.drop_constraint(
        "fk_decision_case_last_schedule_assessment", "decision_case", type_="foreignkey"
    )
    op.drop_table("schedule_assessment")
    op.drop_table("schedule_analysis_policy")
    op.drop_column("decision_case", "last_schedule_assessment_id")
