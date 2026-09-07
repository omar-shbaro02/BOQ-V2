"""Add cost and commercial intelligence."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_cost_commercial"
down_revision: str | None = "0007_schedule_intelligence"
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
        "decision_case", sa.Column("last_cost_assessment_id", postgresql.UUID(), nullable=True)
    )
    op.create_table(
        "cost_analysis_policy",
        uid("id"),
        *scope(),
        sa.Column("policy_version", sa.String(40), nullable=False),
        sa.Column("alignment_tolerance", sa.Numeric(8, 6), nullable=False),
        sa.Column("minimum_earned_ratio_for_forecast", sa.Numeric(8, 6), nullable=False),
        sa.Column("include_accruals_in_recognized_cost", sa.Boolean(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        uid("supersedes_policy_id", True),
        sa.Column("created_by", sa.String(200), nullable=False),
        timestamp("created_at"),
        sa.CheckConstraint(
            "alignment_tolerance >= 0 AND alignment_tolerance <= 1", name="ck_cost_policy_tolerance"
        ),
        sa.CheckConstraint(
            "minimum_earned_ratio_for_forecast > 0 AND minimum_earned_ratio_for_forecast <= 1",
            name="ck_cost_policy_forecast_ratio",
        ),
        *scope_fks(),
        sa.ForeignKeyConstraint(
            ["supersedes_policy_id"], ["cost_analysis_policy.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "policy_version", name="uq_cost_policy_version"),
    )
    indexes("cost_analysis_policy")
    op.create_table(
        "cost_record",
        uid("id"),
        *scope(),
        uid("controlled_object_id"),
        uid("evidence_item_id"),
        uid("authorized_context_id", True),
        sa.Column("record_kind", sa.String(30), nullable=False),
        sa.Column("amount", sa.Numeric(20, 4), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("measurement_basis", sa.String(80), nullable=False),
        sa.Column("reporting_period_start", sa.Date(), nullable=False),
        sa.Column("reporting_period_end", sa.Date(), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("commercial_effect", sa.String(30), nullable=False),
        sa.Column("effect_explanation", sa.Text(), nullable=True),
        sa.Column("semantic_state", sa.String(30), nullable=False),
        sa.Column("truth_type", sa.String(30), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("recorded_by", sa.String(200), nullable=False),
        timestamp("recorded_at"),
        sa.CheckConstraint("amount >= 0", name="ck_cost_record_amount"),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_cost_record_currency"),
        sa.CheckConstraint(
            "reporting_period_end >= reporting_period_start", name="ck_cost_record_period"
        ),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_cost_record_confidence"),
        sa.CheckConstraint(
            "record_kind IN ('APPROVED_BUDGET','AUTHORIZED_CHANGE','COMMITMENT',"
            "'ACTUAL','ACCRUAL','BOQ_VALUE','EARNED_VALUE','PHYSICAL_VALUE')",
            name="ck_cost_record_kind",
        ),
        sa.CheckConstraint(
            "commercial_effect IN ('NONE','TIMING','PROCUREMENT','PREPAYMENT',"
            "'RETENTION','MOBILIZATION')",
            name="ck_cost_record_effect",
        ),
        *scope_fks(),
        sa.ForeignKeyConstraint(
            ["controlled_object_id"], ["controlled_object.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["evidence_item_id"], ["evidence_item.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["authorized_context_id"], ["authorized_context_version.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evidence_item_id", name="uq_cost_record_evidence"),
    )
    indexes("cost_record", ("controlled_object_id", "evidence_item_id"))
    op.create_table(
        "cost_assessment",
        uid("id"),
        *scope(),
        uid("case_id"),
        uid("snapshot_id"),
        uid("budget_context_id"),
        uid("controlled_object_id"),
        sa.Column("assessment_number", sa.Integer(), nullable=False),
        sa.Column("data_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reporting_period_start", sa.Date(), nullable=False),
        sa.Column("reporting_period_end", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("measurement_basis", sa.String(80), nullable=False),
        sa.Column("approved_budget", sa.Numeric(20, 4), nullable=False),
        sa.Column("authorized_changes", sa.Numeric(20, 4), nullable=False),
        sa.Column("current_authorized_budget", sa.Numeric(20, 4), nullable=False),
        sa.Column("commitments", sa.Numeric(20, 4), nullable=False),
        sa.Column("actuals", sa.Numeric(20, 4), nullable=False),
        sa.Column("accruals", sa.Numeric(20, 4), nullable=False),
        sa.Column("recognized_cost", sa.Numeric(20, 4), nullable=False),
        sa.Column("earned_value", sa.Numeric(20, 4), nullable=True),
        sa.Column("physical_progress_ratio", sa.Numeric(12, 8), nullable=True),
        sa.Column("cost_consumption_ratio", sa.Numeric(12, 8), nullable=True),
        sa.Column("progress_value_ratio", sa.Numeric(12, 8), nullable=True),
        sa.Column("alignment_variance_ratio", sa.Numeric(12, 8), nullable=True),
        sa.Column("alignment_status", sa.String(30), nullable=False),
        sa.Column("explained_effects", jsonb, nullable=False),
        sa.Column("unexplained_variance_ratio", sa.Numeric(12, 8), nullable=True),
        sa.Column("forecast_status", sa.String(30), nullable=False),
        sa.Column("forecast_to_complete", sa.Numeric(20, 4), nullable=True),
        sa.Column("estimate_at_completion", sa.Numeric(20, 4), nullable=True),
        sa.Column("assessment_status", sa.String(40), nullable=False),
        sa.Column("maximum_supported_conclusion", sa.String(40), nullable=False),
        sa.Column("input_cost_record_ids", jsonb, nullable=False),
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
        sa.CheckConstraint("assessment_number > 0", name="ck_cost_assessment_number"),
        sa.CheckConstraint(
            "alignment_status IN ('ALIGNED','COST_AHEAD','COST_BEHIND',"
            "'NOT_COMPARABLE','VERIFICATION_REQUIRED')",
            name="ck_cost_alignment_status",
        ),
        sa.CheckConstraint(
            "assessment_status IN ('ASSESSED','VERIFICATION_REQUIRED','INSUFFICIENT')",
            name="ck_cost_assessment_status",
        ),
        sa.CheckConstraint(
            "forecast_status IN ('CALCULATED','NOT_SUPPORTED')", name="ck_cost_forecast_status"
        ),
        sa.CheckConstraint(
            "maximum_supported_conclusion IN ('COST_ONLY_VARIANCE',"
            "'EXPLAINED_DIVERGENCE','FORECAST_EXPOSURE')",
            name="ck_cost_conclusion",
        ),
        sa.CheckConstraint(
            "truth_type IN ('DERIVED_METRIC','CONTRADICTED')", name="ck_cost_output_truth"
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_cost_assessment_confidence"
        ),
        sa.CheckConstraint("request_hash ~ '^[0-9a-f]{64}$'", name="ck_cost_request_hash"),
        *scope_fks(),
        sa.ForeignKeyConstraint(["case_id"], ["decision_case.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["case_snapshot.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["budget_context_id"], ["authorized_context_version.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["controlled_object_id"], ["controlled_object.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "assessment_number", name="uq_cost_assessment_number"),
        sa.UniqueConstraint("case_id", "idempotency_key", name="uq_cost_assessment_idempotency"),
    )
    indexes(
        "cost_assessment", ("case_id", "snapshot_id", "budget_context_id", "controlled_object_id")
    )
    op.create_foreign_key(
        "fk_decision_case_last_cost_assessment",
        "decision_case",
        "cost_assessment",
        ["last_cost_assessment_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.execute("""
        CREATE TRIGGER cost_analysis_policy_append_only
          BEFORE UPDATE OR DELETE ON cost_analysis_policy
          FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
        CREATE TRIGGER cost_record_append_only
          BEFORE UPDATE OR DELETE ON cost_record
          FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
        CREATE TRIGGER cost_assessment_append_only
          BEFORE UPDATE OR DELETE ON cost_assessment
          FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER cost_assessment_append_only ON cost_assessment")
    op.execute("DROP TRIGGER cost_record_append_only ON cost_record")
    op.execute("DROP TRIGGER cost_analysis_policy_append_only ON cost_analysis_policy")
    op.drop_constraint("fk_decision_case_last_cost_assessment", "decision_case", type_="foreignkey")
    op.drop_table("cost_assessment")
    op.drop_table("cost_record")
    op.drop_table("cost_analysis_policy")
    op.drop_column("decision_case", "last_cost_assessment_id")
