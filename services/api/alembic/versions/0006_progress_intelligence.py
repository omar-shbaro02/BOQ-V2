"""Add evidence-backed progress truth and deviation intelligence."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_progress_intelligence"
down_revision: str | None = "0005_decision_cases"
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
        sa.Column("last_progress_evaluation_id", postgresql.UUID(), nullable=True),
    )

    op.create_table(
        "progress_threshold_policy",
        uid("id"),
        *scope(),
        sa.Column("policy_version", sa.String(40), nullable=False),
        sa.Column("deviation_threshold", sa.Numeric(8, 6), nullable=False),
        sa.Column("on_plan_tolerance", sa.Numeric(8, 6), nullable=False),
        sa.Column("persistence_min_observations", sa.Integer(), nullable=False),
        sa.Column("persistence_min_duration_days", sa.Integer(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        uid("supersedes_policy_id", True),
        sa.Column("created_by", sa.String(200), nullable=False),
        timestamp("created_at"),
        sa.CheckConstraint(
            "deviation_threshold > 0 AND deviation_threshold <= 1",
            name="ck_progress_policy_threshold",
        ),
        sa.CheckConstraint(
            "on_plan_tolerance >= 0 AND on_plan_tolerance < deviation_threshold",
            name="ck_progress_policy_tolerance",
        ),
        sa.CheckConstraint(
            "persistence_min_observations >= 2",
            name="ck_progress_policy_observations",
        ),
        sa.CheckConstraint(
            "persistence_min_duration_days >= 1",
            name="ck_progress_policy_duration",
        ),
        *scope_fks(),
        sa.ForeignKeyConstraint(
            ["supersedes_policy_id"], ["progress_threshold_policy.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "policy_version", name="uq_progress_policy_version"),
    )
    indexes("progress_threshold_policy")

    op.create_table(
        "progress_measurement",
        uid("id"),
        *scope(),
        uid("controlled_object_id"),
        uid("evidence_item_id"),
        uid("authorized_context_id", True),
        sa.Column("measurement_kind", sa.String(30), nullable=False),
        sa.Column("measurement_basis", sa.String(80), nullable=False),
        sa.Column("numerator", sa.Numeric(20, 6), nullable=False),
        sa.Column("denominator", sa.Numeric(20, 6), nullable=False),
        sa.Column("completion_ratio", sa.Numeric(12, 8), nullable=False),
        sa.Column("unit", sa.String(30), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("semantic_state", sa.String(30), nullable=False),
        sa.Column("truth_type", sa.String(30), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("recorded_by", sa.String(200), nullable=False),
        timestamp("recorded_at"),
        sa.CheckConstraint(
            "measurement_kind IN ('PLANNED_AUTHORIZED','REPORTED','EXECUTED','VERIFIED',"
            "'ACCEPTED_RELEASED')",
            name="ck_progress_measurement_kind",
        ),
        sa.CheckConstraint("numerator >= 0", name="ck_progress_measurement_numerator"),
        sa.CheckConstraint("denominator > 0", name="ck_progress_measurement_denominator"),
        sa.CheckConstraint(
            "completion_ratio >= 0 AND completion_ratio <= 1",
            name="ck_progress_measurement_ratio",
        ),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_progress_confidence"),
        *scope_fks(),
        sa.ForeignKeyConstraint(
            ["controlled_object_id"], ["controlled_object.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["evidence_item_id"], ["evidence_item.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["authorized_context_id"], ["authorized_context_version.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evidence_item_id", name="uq_progress_measurement_evidence"),
    )
    indexes("progress_measurement")
    op.create_index(
        "ix_progress_measurement_controlled_object_id",
        "progress_measurement",
        ["controlled_object_id"],
    )
    op.create_index(
        "ix_progress_measurement_evidence_item_id",
        "progress_measurement",
        ["evidence_item_id"],
    )

    op.create_table(
        "progress_evaluation",
        uid("id"),
        *scope(),
        uid("case_id"),
        uid("snapshot_id"),
        uid("controlled_object_id"),
        sa.Column("evaluation_number", sa.Integer(), nullable=False),
        sa.Column("data_date", sa.DateTime(timezone=True), nullable=False),
        uid("planned_measurement_id"),
        uid("actual_measurement_id"),
        uid("prior_planned_measurement_id", True),
        uid("prior_actual_measurement_id", True),
        sa.Column("measurement_basis", sa.String(80), nullable=False),
        sa.Column("reconciliation_status", sa.String(40), nullable=False),
        sa.Column("reconciled_measurements", jsonb, nullable=False),
        sa.Column("planned_ratio", sa.Numeric(12, 8), nullable=False),
        sa.Column("actual_ratio", sa.Numeric(12, 8), nullable=False),
        sa.Column("variance_ratio", sa.Numeric(12, 8), nullable=False),
        sa.Column("variance_magnitude", sa.Numeric(12, 8), nullable=False),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("threshold_crossed", sa.Boolean(), nullable=False),
        sa.Column("persistence", sa.String(20), nullable=False),
        sa.Column("trend_direction", sa.String(30), nullable=False),
        sa.Column("supporting_observation_count", sa.Integer(), nullable=False),
        sa.Column("planned_productivity", sa.Numeric(20, 8), nullable=True),
        sa.Column("actual_productivity", sa.Numeric(20, 8), nullable=True),
        sa.Column("productivity_variance_ratio", sa.Numeric(12, 8), nullable=True),
        sa.Column("input_evidence_ids", jsonb, nullable=False),
        sa.Column("input_truth_types", jsonb, nullable=False),
        sa.Column("truth_type", sa.String(30), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("limitations", jsonb, nullable=False),
        sa.Column("policy_version", sa.String(40), nullable=False),
        sa.Column("formula_version", sa.String(40), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("evaluated_by", sa.String(200), nullable=False),
        timestamp("evaluated_at"),
        sa.CheckConstraint("evaluation_number > 0", name="ck_progress_evaluation_number"),
        sa.CheckConstraint(
            "reconciliation_status IN ('RECONCILED','INCOMPARABLE_BASIS',"
            "'INSUFFICIENT_INPUT','VERIFICATION_REQUIRED')",
            name="ck_progress_reconciliation_status",
        ),
        sa.CheckConstraint(
            "direction IN ('AHEAD','ON_PLAN','BEHIND')", name="ck_progress_direction"
        ),
        sa.CheckConstraint(
            "persistence IN ('TRANSIENT','PERSISTENT')", name="ck_progress_persistence"
        ),
        sa.CheckConstraint(
            "trend_direction IN ('FIRST_OBSERVATION','DETERIORATING','STABLE','RECOVERING')",
            name="ck_progress_trend_direction",
        ),
        sa.CheckConstraint("duration_days >= 0", name="ck_progress_duration"),
        sa.CheckConstraint("supporting_observation_count >= 1", name="ck_progress_support_count"),
        sa.CheckConstraint(
            "truth_type IN ('DERIVED_METRIC','CONTRADICTED')",
            name="ck_progress_output_truth",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_progress_eval_confidence"
        ),
        sa.CheckConstraint("request_hash ~ '^[0-9a-f]{64}$'", name="ck_progress_request_hash"),
        *scope_fks(),
        sa.ForeignKeyConstraint(["case_id"], ["decision_case.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["case_snapshot.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["controlled_object_id"], ["controlled_object.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["planned_measurement_id"], ["progress_measurement.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["actual_measurement_id"], ["progress_measurement.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["prior_planned_measurement_id"], ["progress_measurement.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["prior_actual_measurement_id"], ["progress_measurement.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "evaluation_number", name="uq_progress_evaluation_number"),
        sa.UniqueConstraint(
            "case_id", "idempotency_key", name="uq_progress_evaluation_idempotency"
        ),
    )
    indexes("progress_evaluation")
    op.create_index("ix_progress_evaluation_case_id", "progress_evaluation", ["case_id"])
    op.create_index("ix_progress_evaluation_snapshot_id", "progress_evaluation", ["snapshot_id"])
    op.create_index(
        "ix_progress_evaluation_controlled_object_id",
        "progress_evaluation",
        ["controlled_object_id"],
    )
    op.create_foreign_key(
        "fk_decision_case_last_progress_evaluation",
        "decision_case",
        "progress_evaluation",
        ["last_progress_evaluation_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.execute(
        """
        CREATE TRIGGER progress_threshold_policy_append_only
          BEFORE UPDATE OR DELETE ON progress_threshold_policy
          FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
        CREATE TRIGGER progress_measurement_append_only
          BEFORE UPDATE OR DELETE ON progress_measurement
          FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
        CREATE TRIGGER progress_evaluation_append_only
          BEFORE UPDATE OR DELETE ON progress_evaluation
          FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER progress_evaluation_append_only ON progress_evaluation")
    op.execute("DROP TRIGGER progress_measurement_append_only ON progress_measurement")
    op.execute("DROP TRIGGER progress_threshold_policy_append_only ON progress_threshold_policy")
    op.drop_constraint(
        "fk_decision_case_last_progress_evaluation", "decision_case", type_="foreignkey"
    )
    op.drop_table("progress_evaluation")
    op.drop_table("progress_measurement")
    op.drop_table("progress_threshold_policy")
    op.drop_column("decision_case", "last_progress_evaluation_id")
