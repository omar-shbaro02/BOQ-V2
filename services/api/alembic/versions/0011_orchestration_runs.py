"""Add immutable Phase 10 orchestration and specialist run records."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_orchestration_runs"
down_revision: str | None = "0010_impact_priority"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.add_column("decision_case", sa.Column("last_orchestration_run_id", postgresql.UUID()))
    op.create_table(
        "orchestration_run",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(), nullable=False),
        sa.Column("project_id", postgresql.UUID(), nullable=False),
        sa.Column("case_id", postgresql.UUID(), nullable=False),
        sa.Column("snapshot_id", postgresql.UUID(), nullable=False),
        sa.Column("retry_of_run_id", postgresql.UUID()),
        sa.Column("run_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("readiness", sa.String(50), nullable=False),
        sa.Column("recommended_disposition", sa.String(20)),
        sa.Column("alternative_dispositions", jsonb, nullable=False),
        sa.Column("blockers", jsonb, nullable=False),
        sa.Column("limitations", jsonb, nullable=False),
        sa.Column("contradiction_findings", jsonb, nullable=False),
        sa.Column("case_brief", jsonb, nullable=False),
        sa.Column("policy_versions", jsonb, nullable=False),
        sa.Column("formula_version", sa.String(40), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["case_id"], ["decision_case.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["case_snapshot.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["retry_of_run_id"], ["orchestration_run.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("case_id", "run_number", name="uq_orchestration_run_number"),
        sa.UniqueConstraint("case_id", "idempotency_key", name="uq_orchestration_idempotency"),
        sa.CheckConstraint("run_number > 0", name="ck_orchestration_run_number"),
        sa.CheckConstraint("request_hash ~ '^[0-9a-f]{64}$'", name="ck_orchestration_request_hash"),
    )
    op.create_table(
        "specialist_run",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(), nullable=False),
        sa.Column("project_id", postgresql.UUID(), nullable=False),
        sa.Column("orchestration_run_id", postgresql.UUID(), nullable=False),
        sa.Column("case_id", postgresql.UUID(), nullable=False),
        sa.Column("snapshot_id", postgresql.UUID(), nullable=False),
        sa.Column("specialist_kind", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("input_references", jsonb, nullable=False),
        sa.Column("output_references", jsonb, nullable=False),
        sa.Column("findings", jsonb, nullable=False),
        sa.Column("calculations", jsonb, nullable=False),
        sa.Column("evidence_references", jsonb, nullable=False),
        sa.Column("truth_labels", jsonb, nullable=False),
        sa.Column("assumptions", jsonb, nullable=False),
        sa.Column("contradictions", jsonb, nullable=False),
        sa.Column("confidence", sa.Numeric(8, 6), nullable=False),
        sa.Column("limitations", jsonb, nullable=False),
        sa.Column("requested_evidence", jsonb, nullable=False),
        sa.Column("contract_version", sa.String(40), nullable=False),
        sa.Column("error_class", sa.String(80)),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["orchestration_run_id"], ["orchestration_run.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["case_id"], ["decision_case.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["case_snapshot.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "orchestration_run_id", "specialist_kind", name="uq_orchestration_specialist_kind"
        ),
        sa.CheckConstraint("attempt > 0", name="ck_specialist_attempt"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_specialist_confidence"),
    )
    for table in ("orchestration_run", "specialist_run"):
        op.create_index(f"ix_{table}_organization_id", table, ["organization_id"])
        op.create_index(f"ix_{table}_project_id", table, ["project_id"])
        op.create_index(f"ix_{table}_case_id", table, ["case_id"])
        op.create_index(f"ix_{table}_snapshot_id", table, ["snapshot_id"])
    op.create_index(
        "ix_specialist_run_orchestration_run_id", "specialist_run", ["orchestration_run_id"]
    )
    op.create_index(
        "ix_orchestration_run_retry_of_run_id", "orchestration_run", ["retry_of_run_id"]
    )
    op.create_foreign_key(
        "fk_decision_case_last_orchestration_run",
        "decision_case",
        "orchestration_run",
        ["last_orchestration_run_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.execute("""
        CREATE TRIGGER orchestration_run_append_only
          BEFORE UPDATE OR DELETE ON orchestration_run
          FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
        CREATE TRIGGER specialist_run_append_only
          BEFORE UPDATE OR DELETE ON specialist_run
          FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER specialist_run_append_only ON specialist_run")
    op.execute("DROP TRIGGER orchestration_run_append_only ON orchestration_run")
    op.drop_constraint(
        "fk_decision_case_last_orchestration_run", "decision_case", type_="foreignkey"
    )
    op.drop_table("specialist_run")
    op.drop_table("orchestration_run")
    op.drop_column("decision_case", "last_orchestration_run_id")
