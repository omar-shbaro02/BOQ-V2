"""Add versioned forecasts and scenarios."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_forecast_scenarios"
down_revision: str | None = "0008_cost_commercial"
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
        "decision_case",
        sa.Column("last_forecast_projection_id", postgresql.UUID(), nullable=True),
    )
    op.create_table(
        "forecast_policy",
        uid("id"),
        *scope(),
        sa.Column("policy_version", sa.String(40), nullable=False),
        sa.Column("lower_rate_factor", sa.Numeric(8, 6), nullable=False),
        sa.Column("upper_rate_factor", sa.Numeric(8, 6), nullable=False),
        sa.Column("lower_cost_factor", sa.Numeric(8, 6), nullable=False),
        sa.Column("upper_cost_factor", sa.Numeric(8, 6), nullable=False),
        sa.Column("confidence_decay_per_30_days", sa.Numeric(8, 6), nullable=False),
        sa.Column("confidence_floor", sa.Numeric(8, 6), nullable=False),
        sa.Column("maximum_horizon_days", sa.Integer(), nullable=False),
        sa.Column("validity_days", sa.Integer(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        uid("supersedes_policy_id", True),
        sa.Column("created_by", sa.String(200), nullable=False),
        timestamp("created_at"),
        sa.CheckConstraint(
            "lower_rate_factor > 0 AND lower_rate_factor < 1", name="ck_forecast_lower_rate"
        ),
        sa.CheckConstraint(
            "upper_rate_factor > 1 AND upper_rate_factor <= 3", name="ck_forecast_upper_rate"
        ),
        sa.CheckConstraint(
            "lower_cost_factor > 0 AND lower_cost_factor < 1", name="ck_forecast_lower_cost"
        ),
        sa.CheckConstraint(
            "upper_cost_factor > 1 AND upper_cost_factor <= 3", name="ck_forecast_upper_cost"
        ),
        sa.CheckConstraint(
            "confidence_decay_per_30_days >= 0 AND confidence_decay_per_30_days < 1",
            name="ck_forecast_confidence_decay",
        ),
        sa.CheckConstraint(
            "confidence_floor >= 0 AND confidence_floor <= 1", name="ck_forecast_confidence_floor"
        ),
        sa.CheckConstraint("maximum_horizon_days > 0", name="ck_forecast_max_horizon"),
        sa.CheckConstraint("validity_days > 0", name="ck_forecast_validity_days"),
        *scope_fks(),
        sa.ForeignKeyConstraint(
            ["supersedes_policy_id"], ["forecast_policy.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "policy_version", name="uq_forecast_policy_version"),
    )
    indexes("forecast_policy")
    op.create_table(
        "forecast_projection",
        uid("id"),
        *scope(),
        uid("case_id"),
        uid("snapshot_id"),
        uid("controlled_object_id"),
        uid("progress_evaluation_id", True),
        uid("schedule_assessment_id", True),
        uid("cost_assessment_id", True),
        uid("active_response_id", True),
        sa.Column("forecast_number", sa.Integer(), nullable=False),
        sa.Column("target", sa.String(40), nullable=False),
        sa.Column("scenario_type", sa.String(40), nullable=False),
        sa.Column("method", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("semantic_state", sa.String(20), nullable=False),
        sa.Column("truth_type", sa.String(30), nullable=False),
        sa.Column("data_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("horizon_end", sa.Date(), nullable=False),
        sa.Column("horizon_days", sa.Integer(), nullable=False),
        sa.Column("result_unit", sa.String(30), nullable=False),
        sa.Column("result_point", sa.String(80), nullable=False),
        sa.Column("result_lower", sa.String(80), nullable=False),
        sa.Column("result_upper", sa.String(80), nullable=False),
        sa.Column("input_values", jsonb, nullable=False),
        sa.Column("input_evidence_ids", jsonb, nullable=False),
        sa.Column("assumptions", jsonb, nullable=False),
        sa.Column("scenario_parameters", jsonb, nullable=False),
        sa.Column("limitations", jsonb, nullable=False),
        sa.Column("upstream_confidence", sa.Numeric(8, 6), nullable=False),
        sa.Column("horizon_confidence", sa.Numeric(8, 6), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recalculation_triggers", jsonb, nullable=False),
        sa.Column("policy_version", sa.String(40), nullable=False),
        sa.Column("formula_version", sa.String(40), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        timestamp("created_at"),
        sa.CheckConstraint("forecast_number > 0", name="ck_forecast_number"),
        sa.CheckConstraint("horizon_days > 0", name="ck_forecast_horizon"),
        sa.CheckConstraint(
            "target IN ('PRODUCTION_COMPLETION_DATE','SCHEDULE_COMPLETION_DATE',"
            "'ESTIMATE_AT_COMPLETION')",
            name="ck_forecast_target",
        ),
        sa.CheckConstraint(
            "scenario_type IN ('CONTINUED_PERFORMANCE','ACTIVE_RESPONSE','HYPOTHETICAL')",
            name="ck_forecast_scenario_type",
        ),
        sa.CheckConstraint(
            "method IN ('LINEAR_PRODUCTION_RATE','SCHEDULE_DELAY_PROPAGATION',"
            "'COST_PERFORMANCE_INDEX')",
            name="ck_forecast_method",
        ),
        sa.CheckConstraint("status IN ('CALCULATED','LIMITED')", name="ck_forecast_status"),
        sa.CheckConstraint(
            "semantic_state IN ('FORECAST','SCENARIO')", name="ck_forecast_semantic_state"
        ),
        sa.CheckConstraint("truth_type = 'SCENARIO_ESTIMATE'", name="ck_forecast_truth_type"),
        sa.CheckConstraint(
            "upstream_confidence >= 0 AND upstream_confidence <= 1",
            name="ck_forecast_upstream_confidence",
        ),
        sa.CheckConstraint(
            "horizon_confidence >= 0 AND horizon_confidence <= upstream_confidence",
            name="ck_forecast_horizon_confidence",
        ),
        sa.CheckConstraint("request_hash ~ '^[0-9a-f]{64}$'", name="ck_forecast_request_hash"),
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
            ["active_response_id"], ["case_active_response.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "forecast_number", name="uq_forecast_number"),
        sa.UniqueConstraint("case_id", "idempotency_key", name="uq_forecast_idempotency"),
    )
    indexes("forecast_projection", ("case_id", "snapshot_id", "controlled_object_id"))
    op.create_foreign_key(
        "fk_decision_case_last_forecast_projection",
        "decision_case",
        "forecast_projection",
        ["last_forecast_projection_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.execute("""
        CREATE TRIGGER forecast_policy_append_only
          BEFORE UPDATE OR DELETE ON forecast_policy
          FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
        CREATE TRIGGER forecast_projection_append_only
          BEFORE UPDATE OR DELETE ON forecast_projection
          FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER forecast_projection_append_only ON forecast_projection")
    op.execute("DROP TRIGGER forecast_policy_append_only ON forecast_policy")
    op.drop_constraint(
        "fk_decision_case_last_forecast_projection", "decision_case", type_="foreignkey"
    )
    op.drop_table("forecast_projection")
    op.drop_table("forecast_policy")
    op.drop_column("decision_case", "last_forecast_projection_id")
