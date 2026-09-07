"""Create Phase 3 signal screening, correlation, case-shell, and outbox tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_signals"
down_revision: str | None = "0003_evidence"
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
    op.create_table(
        "signal",
        uid("id"),
        *scope(),
        uid("controlled_object_id", True),
        sa.Column("signal_type", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("source_field", sa.String(120), nullable=False),
        sa.Column("source_evidence_ids", jsonb, nullable=False),
        uid("source_contradiction_id", True),
        sa.Column("observed_value", jsonb, nullable=False),
        sa.Column("detector_details", jsonb, nullable=False),
        sa.Column("materiality_candidate", sa.String(20), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("occurrence_count", sa.Integer(), nullable=False),
        sa.Column("detector_name", sa.String(100), nullable=False),
        sa.Column("detector_version", sa.String(40), nullable=False),
        sa.Column("first_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deferred_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("workflow_version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        timestamp("created_at"),
        timestamp("updated_at"),
        sa.CheckConstraint(
            "signal_type IN ('PROGRESS_VARIANCE','SCHEDULE_VARIANCE','COST_VARIANCE',"
            "'EVIDENCE_CONFLICT','MILESTONE_EXPOSURE')",
            name="ck_signal_type",
        ),
        sa.CheckConstraint(
            "status IN ('CANDIDATE','SCREENED','DEFERRED','DISMISSED','CORRELATED','EXPIRED')",
            name="ck_signal_status",
        ),
        sa.CheckConstraint(
            "materiality_candidate IN ('IMMATERIAL','LOW','MEDIUM','HIGH','CRITICAL')",
            name="ck_signal_materiality",
        ),
        sa.CheckConstraint("fingerprint ~ '^[0-9a-f]{64}$'", name="ck_signal_fingerprint"),
        sa.CheckConstraint("occurrence_count > 0", name="ck_signal_occurrences"),
        sa.CheckConstraint("workflow_version > 0", name="ck_signal_workflow_version"),
        sa.CheckConstraint("expires_at > first_observed_at", name="ck_signal_expiry"),
        *scope_fks(),
        sa.ForeignKeyConstraint(
            ["controlled_object_id"], ["controlled_object.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_contradiction_id"], ["contradiction.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "fingerprint", name="uq_signal_project_fingerprint"),
    )
    indexes("signal")
    for column in ("controlled_object_id", "signal_type", "status"):
        op.create_index(f"ix_signal_{column}", "signal", [column])

    op.create_table(
        "signal_evidence",
        uid("signal_id"),
        uid("evidence_item_id"),
        sa.ForeignKeyConstraint(["signal_id"], ["signal.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evidence_item_id"], ["evidence_item.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("signal_id", "evidence_item_id"),
    )
    op.create_table(
        "signal_detection_run",
        uid("id"),
        *scope(),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("detector_version", sa.String(40), nullable=False),
        sa.Column("signal_ids", jsonb, nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        timestamp("created_at"),
        *scope_fks(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "idempotency_key", name="uq_detection_run_idempotency"),
    )
    indexes("signal_detection_run")
    op.create_table(
        "signal_screening_decision",
        uid("id"),
        *scope(),
        uid("signal_id"),
        sa.Column("signal_version", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("reason_code", sa.String(50), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("materiality_candidate", sa.String(20), nullable=False),
        sa.Column("defer_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by", sa.String(200), nullable=False),
        timestamp("decided_at"),
        sa.CheckConstraint("outcome IN ('RELEVANT','DEFER','DISMISS')", name="ck_screen_outcome"),
        sa.CheckConstraint(
            "materiality_candidate IN ('IMMATERIAL','LOW','MEDIUM','HIGH','CRITICAL')",
            name="ck_screen_materiality",
        ),
        sa.CheckConstraint(
            "(outcome = 'DEFER' AND defer_until IS NOT NULL) OR "
            "(outcome <> 'DEFER' AND defer_until IS NULL)",
            name="ck_screen_defer",
        ),
        *scope_fks(),
        sa.ForeignKeyConstraint(["signal_id"], ["signal.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    indexes("signal_screening_decision")
    op.create_index(
        "ix_signal_screening_decision_signal_id", "signal_screening_decision", ["signal_id"]
    )

    op.create_table(
        "decision_case",
        uid("id"),
        *scope(),
        sa.Column("case_number", sa.String(40), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("case_type", sa.String(60), nullable=False),
        sa.Column("lifecycle", sa.String(30), nullable=False),
        sa.Column("owner_actor_id", sa.String(200), nullable=False),
        uid("parent_case_id", True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        timestamp("opened_at"),
        sa.CheckConstraint("lifecycle = 'OPEN'", name="ck_case_shell_lifecycle"),
        sa.CheckConstraint("version > 0", name="ck_case_shell_version"),
        *scope_fks(),
        sa.ForeignKeyConstraint(["parent_case_id"], ["decision_case.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "case_number", name="uq_decision_case_number"),
    )
    indexes("decision_case")
    op.create_index("ix_decision_case_parent_case_id", "decision_case", ["parent_case_id"])
    op.create_table(
        "decision_case_controlled_object",
        uid("case_id"),
        uid("controlled_object_id"),
        sa.ForeignKeyConstraint(["case_id"], ["decision_case.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["controlled_object_id"], ["controlled_object.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("case_id", "controlled_object_id"),
    )
    op.create_table(
        "decision_case_signal",
        uid("case_id"),
        uid("signal_id"),
        sa.Column("correlation_rationale", sa.Text(), nullable=False),
        sa.Column("linked_by", sa.String(200), nullable=False),
        timestamp("linked_at"),
        sa.ForeignKeyConstraint(["case_id"], ["decision_case.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["signal_id"], ["signal.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("case_id", "signal_id"),
    )

    op.create_table(
        "signal_correlation_suggestion",
        uid("id"),
        *scope(),
        uid("signal_id"),
        sa.Column("signal_version", sa.Integer(), nullable=False),
        sa.Column("suggested_outcome", sa.String(40), nullable=False),
        uid("target_case_id", True),
        sa.Column("child_case_ids", jsonb, nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        timestamp("created_at"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_correlation_confidence"),
        sa.CheckConstraint(
            "status IN ('PENDING','ACCEPTED','REJECTED')", name="ck_correlation_status"
        ),
        *scope_fks(),
        sa.ForeignKeyConstraint(["signal_id"], ["signal.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["target_case_id"], ["decision_case.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("signal_id", "signal_version", name="uq_correlation_signal_version"),
    )
    indexes("signal_correlation_suggestion")
    op.create_index(
        "ix_signal_correlation_suggestion_signal_id", "signal_correlation_suggestion", ["signal_id"]
    )
    op.create_table(
        "signal_correlation_review",
        uid("id"),
        *scope(),
        uid("suggestion_id"),
        sa.Column("selected_outcome", sa.String(40), nullable=True),
        uid("target_case_id", True),
        uid("created_case_id", True),
        sa.Column("child_case_ids", jsonb, nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("reviewed_by", sa.String(200), nullable=False),
        timestamp("reviewed_at"),
        sa.CheckConstraint("status IN ('ACCEPTED','REJECTED')", name="ck_review_status"),
        sa.CheckConstraint(
            "(status = 'REJECTED' AND selected_outcome IS NULL) OR "
            "(status = 'ACCEPTED' AND selected_outcome IS NOT NULL)",
            name="ck_review_outcome",
        ),
        *scope_fks(),
        sa.ForeignKeyConstraint(
            ["suggestion_id"], ["signal_correlation_suggestion.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["target_case_id"], ["decision_case.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_case_id"], ["decision_case.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("suggestion_id"),
    )
    indexes("signal_correlation_review")

    op.create_table(
        "outbox_event",
        uid("event_id"),
        *scope(),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("schema_version", sa.String(20), nullable=False),
        sa.Column("aggregate_type", sa.String(60), nullable=False),
        uid("aggregate_id"),
        sa.Column("aggregate_version", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.String(200), nullable=False),
        uid("correlation_id"),
        uid("causation_id", True),
        sa.Column("data_classification", sa.String(30), nullable=False),
        sa.Column("payload", jsonb, nullable=False),
        timestamp("occurred_at"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("aggregate_version > 0", name="ck_outbox_aggregate_version"),
        *scope_fks(),
        sa.PrimaryKeyConstraint("event_id"),
    )
    indexes("outbox_event")
    for column in ("event_type", "aggregate_id"):
        op.create_index(f"ix_outbox_event_{column}", "outbox_event", [column])

    op.execute(
        """
        CREATE TRIGGER signal_detection_run_append_only
          BEFORE UPDATE OR DELETE ON signal_detection_run
          FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
        CREATE TRIGGER signal_screening_decision_append_only
          BEFORE UPDATE OR DELETE ON signal_screening_decision
          FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
        CREATE TRIGGER signal_correlation_review_append_only
          BEFORE UPDATE OR DELETE ON signal_correlation_review
          FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
        CREATE TRIGGER outbox_event_no_delete
          BEFORE DELETE ON outbox_event
          FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER outbox_event_no_delete ON outbox_event")
    op.execute("DROP TRIGGER signal_correlation_review_append_only ON signal_correlation_review")
    op.execute("DROP TRIGGER signal_screening_decision_append_only ON signal_screening_decision")
    op.execute("DROP TRIGGER signal_detection_run_append_only ON signal_detection_run")
    for table in (
        "outbox_event",
        "signal_correlation_review",
        "signal_correlation_suggestion",
        "decision_case_signal",
        "decision_case_controlled_object",
        "decision_case",
        "signal_screening_decision",
        "signal_detection_run",
        "signal_evidence",
        "signal",
    ):
        op.drop_table(table)
