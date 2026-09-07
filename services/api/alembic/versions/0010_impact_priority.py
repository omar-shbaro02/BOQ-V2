"""Add consequence, confidence, decision clock, and priority assessments."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_impact_priority"
down_revision: str | None = "0009_forecast_scenarios"
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


def indexes(table: str, extra: tuple[str, ...] = ()) -> None:
    op.create_index(f"ix_{table}_organization_id", table, ["organization_id"])
    op.create_index(f"ix_{table}_project_id", table, ["project_id"])
    for column in extra:
        op.create_index(f"ix_{table}_{column}", table, [column])


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.add_column(
        "decision_case", sa.Column("last_impact_assessment_id", postgresql.UUID(), nullable=True)
    )
    op.create_table(
        "impact_priority_policy",
        uid("id"),
        *scope(),
        sa.Column("policy_version", sa.String(40), nullable=False),
        sa.Column("medium_cost_exposure_ratio", sa.Numeric(8, 6), nullable=False),
        sa.Column("high_cost_exposure_ratio", sa.Numeric(8, 6), nullable=False),
        sa.Column("critical_cost_exposure_ratio", sa.Numeric(8, 6), nullable=False),
        sa.Column("elevated_margin_days", sa.Integer(), nullable=False),
        sa.Column("urgent_margin_days", sa.Integer(), nullable=False),
        sa.Column("active_response_score_reduction", sa.Numeric(8, 3), nullable=False),
        sa.Column("cross_cutting_bonus_per_object", sa.Numeric(8, 3), nullable=False),
        sa.Column("medium_priority_score", sa.Numeric(8, 3), nullable=False),
        sa.Column("high_priority_score", sa.Numeric(8, 3), nullable=False),
        sa.Column("critical_priority_score", sa.Numeric(8, 3), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        uid("supersedes_policy_id", True),
        sa.Column("created_by", sa.String(200), nullable=False),
        timestamp("created_at"),
        sa.CheckConstraint(
            "medium_cost_exposure_ratio < high_cost_exposure_ratio AND "
            "high_cost_exposure_ratio < critical_cost_exposure_ratio",
            name="ck_impact_cost_thresholds",
        ),
        sa.CheckConstraint(
            "urgent_margin_days < elevated_margin_days", name="ck_impact_margin_thresholds"
        ),
        sa.CheckConstraint(
            "medium_priority_score < high_priority_score AND "
            "high_priority_score < critical_priority_score",
            name="ck_impact_priority_thresholds",
        ),
        *scope_fks(),
        sa.ForeignKeyConstraint(
            ["supersedes_policy_id"], ["impact_priority_policy.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "policy_version", name="uq_impact_policy_version"),
    )
    indexes("impact_priority_policy")
    op.create_table(
        "confidence_override",
        uid("id"),
        *scope(),
        uid("case_id"),
        uid("snapshot_id"),
        sa.Column("upstream_ceiling", sa.Numeric(8, 6), nullable=False),
        sa.Column("approved_confidence", sa.Numeric(8, 6), nullable=False),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("approved_by", sa.String(200), nullable=False),
        timestamp("approved_at"),
        sa.CheckConstraint(
            "upstream_ceiling >= 0 AND upstream_ceiling <= 1", name="ck_override_ceiling"
        ),
        sa.CheckConstraint(
            "approved_confidence > upstream_ceiling AND approved_confidence <= 1",
            name="ck_override_confidence",
        ),
        *scope_fks(),
        sa.ForeignKeyConstraint(["case_id"], ["decision_case.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["case_snapshot.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    indexes("confidence_override", ("case_id", "snapshot_id"))
    op.create_table(
        "impact_assessment",
        uid("id"),
        *scope(),
        uid("case_id"),
        uid("snapshot_id"),
        uid("controlled_object_id"),
        uid("progress_evaluation_id", True),
        uid("schedule_assessment_id", True),
        uid("cost_assessment_id", True),
        sa.Column("forecast_projection_ids", jsonb, nullable=False),
        uid("confidence_override_id", True),
        sa.Column("assessment_number", sa.Integer(), nullable=False),
        sa.Column("consequence_paths", jsonb, nullable=False),
        sa.Column("consequence_severity", sa.String(20), nullable=False),
        sa.Column("decision_clocks", jsonb, nullable=False),
        sa.Column("response_lead_days", sa.Integer(), nullable=False),
        sa.Column("urgency_margin_days", sa.Integer(), nullable=True),
        sa.Column("urgency", sa.String(20), nullable=False),
        sa.Column("truth_confidence", sa.Numeric(8, 6), nullable=False),
        sa.Column("forecast_confidence", sa.Numeric(8, 6), nullable=False),
        sa.Column("consequence_confidence", sa.Numeric(8, 6), nullable=False),
        sa.Column("upstream_confidence_ceiling", sa.Numeric(8, 6), nullable=False),
        sa.Column("overall_confidence", sa.Numeric(8, 6), nullable=False),
        sa.Column("cross_cutting_reach", sa.Integer(), nullable=False),
        sa.Column("active_response_count", sa.Integer(), nullable=False),
        sa.Column("priority_score", sa.Numeric(8, 3), nullable=False),
        sa.Column("priority_band", sa.String(20), nullable=False),
        sa.Column("priority_reason_codes", jsonb, nullable=False),
        sa.Column("assessment_status", sa.String(30), nullable=False),
        sa.Column("limitations", jsonb, nullable=False),
        sa.Column("policy_version", sa.String(40), nullable=False),
        sa.Column("formula_version", sa.String(40), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("assessed_by", sa.String(200), nullable=False),
        timestamp("assessed_at"),
        sa.CheckConstraint("assessment_number > 0", name="ck_impact_number"),
        sa.CheckConstraint("response_lead_days >= 0", name="ck_impact_response_lead"),
        sa.CheckConstraint("cross_cutting_reach > 0", name="ck_impact_reach"),
        sa.CheckConstraint("active_response_count >= 0", name="ck_impact_active_responses"),
        sa.CheckConstraint(
            "priority_score >= 0 AND priority_score <= 100", name="ck_impact_priority_score"
        ),
        sa.CheckConstraint(
            "truth_confidence >= 0 AND truth_confidence <= 1 AND forecast_confidence >= 0 AND "
            "forecast_confidence <= 1 AND consequence_confidence >= 0 AND "
            "consequence_confidence <= 1 AND "
            "upstream_confidence_ceiling >= 0 AND upstream_confidence_ceiling <= 1 AND "
            "overall_confidence >= 0 AND overall_confidence <= 1",
            name="ck_impact_confidences",
        ),
        sa.CheckConstraint(
            "consequence_severity IN ('NONE','LOW','MEDIUM','HIGH','CRITICAL')",
            name="ck_impact_severity",
        ),
        sa.CheckConstraint(
            "urgency IN ('NONE','ROUTINE','ELEVATED','URGENT','IMMEDIATE')",
            name="ck_impact_urgency",
        ),
        sa.CheckConstraint(
            "priority_band IN ('LOW','MEDIUM','HIGH','CRITICAL')", name="ck_impact_band"
        ),
        sa.CheckConstraint(
            "assessment_status IN ('ASSESSED','LIMITED','VERIFICATION_REQUIRED')",
            name="ck_impact_status",
        ),
        sa.CheckConstraint("request_hash ~ '^[0-9a-f]{64}$'", name="ck_impact_request_hash"),
        *scope_fks(),
        sa.ForeignKeyConstraint(["case_id"], ["decision_case.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["case_snapshot.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["controlled_object_id"], ["controlled_object.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["progress_evaluation_id"], ["progress_evaluation.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["schedule_assessment_id"], ["schedule_assessment.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["cost_assessment_id"], ["cost_assessment.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["confidence_override_id"], ["confidence_override.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "assessment_number", name="uq_impact_assessment_number"),
        sa.UniqueConstraint("case_id", "idempotency_key", name="uq_impact_assessment_idempotency"),
    )
    indexes("impact_assessment", ("case_id", "snapshot_id", "controlled_object_id"))
    op.create_foreign_key(
        "fk_decision_case_last_impact_assessment",
        "decision_case",
        "impact_assessment",
        ["last_impact_assessment_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.execute("""
        CREATE TRIGGER impact_priority_policy_append_only
          BEFORE UPDATE OR DELETE ON impact_priority_policy
          FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
        CREATE TRIGGER confidence_override_append_only
          BEFORE UPDATE OR DELETE ON confidence_override
          FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
        CREATE TRIGGER impact_assessment_append_only
          BEFORE UPDATE OR DELETE ON impact_assessment
          FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER impact_assessment_append_only ON impact_assessment")
    op.execute("DROP TRIGGER confidence_override_append_only ON confidence_override")
    op.execute("DROP TRIGGER impact_priority_policy_append_only ON impact_priority_policy")
    op.drop_constraint(
        "fk_decision_case_last_impact_assessment", "decision_case", type_="foreignkey"
    )
    op.drop_table("impact_assessment")
    op.drop_table("confidence_override")
    op.drop_table("impact_priority_policy")
    op.drop_column("decision_case", "last_impact_assessment_id")
