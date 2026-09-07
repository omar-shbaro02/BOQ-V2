"""Expand case shells into Phase 4 lifecycle and sufficiency aggregates."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_decision_cases"
down_revision: str | None = "0004_signals"
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
    op.drop_constraint("ck_case_shell_lifecycle", "decision_case", type_="check")
    op.add_column("decision_case", sa.Column("readiness", sa.String(50), nullable=True))
    op.add_column(
        "decision_case",
        sa.Column(
            "governance_state",
            sa.String(40),
            server_default="HUMAN_REVIEW_REQUIRED",
            nullable=False,
        ),
    )
    op.add_column(
        "decision_case",
        sa.Column(
            "autonomy_class",
            sa.String(40),
            server_default="A1_ANALYTICAL_AUTONOMY",
            nullable=False,
        ),
    )
    for name, length in (
        ("blocked_from_lifecycle", 30),
        ("blocker_code", 80),
        ("outcome_reference", 200),
        ("reopen_trigger", 50),
    ):
        op.add_column("decision_case", sa.Column(name, sa.String(length), nullable=True))
    op.add_column("decision_case", sa.Column("blocker_description", sa.Text(), nullable=True))
    op.add_column("decision_case", sa.Column("last_snapshot_id", postgresql.UUID(), nullable=True))
    op.add_column("decision_case", sa.Column("close_reason", sa.Text(), nullable=True))
    op.add_column(
        "decision_case", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("decision_case", sa.Column("reopen_reason", sa.Text(), nullable=True))
    op.add_column(
        "decision_case", sa.Column("reopened_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_check_constraint(
        "ck_decision_case_lifecycle",
        "decision_case",
        "lifecycle IN ('OPEN','EVIDENCE_ASSEMBLY','ANALYSIS','REVIEW','DECISION_READY',"
        "'HUMAN_DISPOSITION','RESPONSE_ESCALATION','OUTCOME_MONITORING','CLOSED','BLOCKED','REOPENED')",
    )
    op.create_check_constraint(
        "ck_decision_case_readiness",
        "decision_case",
        "readiness IS NULL OR readiness IN ('DECISION_READY','DECISION_READY_WITH_LIMITATIONS',"
        "'VERIFICATION_REQUIRED','INSUFFICIENT')",
    )
    op.create_check_constraint(
        "ck_decision_case_governance_state",
        "decision_case",
        "governance_state IN ('ANALYSIS_AUTHORIZED','VERIFICATION_REQUIRED',"
        "'HUMAN_REVIEW_REQUIRED','APPROVAL_REQUIRED','ESCALATION_REQUIRED',"
        "'GOVERNANCE_BLOCKED','AUTHORIZED_TO_PROCEED')",
    )
    op.create_check_constraint(
        "ck_decision_case_autonomy_class",
        "decision_case",
        "autonomy_class IN ('A0_OBSERVATION_READ_ONLY','A1_ANALYTICAL_AUTONOMY',"
        "'A2_ADVISORY_AUTONOMY','A3_CONTROLLED_EXECUTION','A4_HUMAN_RESERVED')",
    )
    op.create_check_constraint(
        "ck_decision_case_reopen_trigger",
        "decision_case",
        "reopen_trigger IS NULL OR reopen_trigger IN ('NEW_MATERIAL_EVIDENCE',"
        "'FORECAST_EXPIRED','RESPONSE_FAILED','CONSEQUENCE_RENEWED',"
        "'ADMINISTRATIVE_CORRECTION')",
    )
    op.create_check_constraint(
        "ck_decision_case_close_basis",
        "decision_case",
        "lifecycle <> 'CLOSED' OR (closed_at IS NOT NULL AND close_reason IS NOT NULL)",
    )

    op.create_table(
        "case_evidence_attachment",
        uid("case_id"),
        uid("evidence_item_id"),
        sa.Column("attachment_reason", sa.Text(), nullable=False),
        sa.Column("attached_by", sa.String(200), nullable=False),
        timestamp("attached_at"),
        sa.ForeignKeyConstraint(["case_id"], ["decision_case.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evidence_item_id"], ["evidence_item.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("case_id", "evidence_item_id"),
    )
    op.create_table(
        "case_active_response",
        uid("id"),
        *scope(),
        uid("case_id"),
        sa.Column("response_type", sa.String(80), nullable=False),
        sa.Column("authorization_reference", sa.String(200), nullable=False),
        sa.Column("owner_actor_id", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("details", jsonb, nullable=False),
        sa.Column("recorded_by", sa.String(200), nullable=False),
        timestamp("recorded_at"),
        sa.CheckConstraint(
            "status IN ('ACTIVE','COMPLETED','FAILED','CANCELLED')", name="ck_case_response_status"
        ),
        sa.CheckConstraint(
            "effective_until IS NULL OR effective_until > effective_from",
            name="ck_case_response_window",
        ),
        *scope_fks(),
        sa.ForeignKeyConstraint(["case_id"], ["decision_case.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    indexes("case_active_response")
    op.create_index("ix_case_active_response_case_id", "case_active_response", ["case_id"])

    op.create_table(
        "case_snapshot",
        uid("id"),
        *scope(),
        uid("case_id"),
        sa.Column("snapshot_number", sa.Integer(), nullable=False),
        sa.Column("case_version", sa.Integer(), nullable=False),
        sa.Column("data_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("controlled_object_ids", jsonb, nullable=False),
        sa.Column("signal_ids", jsonb, nullable=False),
        sa.Column("evidence_item_ids", jsonb, nullable=False),
        sa.Column("contradiction_ids", jsonb, nullable=False),
        sa.Column("authorized_context_refs", jsonb, nullable=False),
        sa.Column("active_response_ids", jsonb, nullable=False),
        sa.Column("baseline_validity", sa.String(30), nullable=False),
        sa.Column("policy_version", sa.String(40), nullable=False),
        sa.Column("snapshot_hash", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        timestamp("created_at"),
        sa.CheckConstraint("snapshot_number > 0", name="ck_case_snapshot_number"),
        sa.CheckConstraint("case_version > 0", name="ck_case_snapshot_case_version"),
        sa.CheckConstraint("snapshot_hash ~ '^[0-9a-f]{64}$'", name="ck_case_snapshot_hash"),
        sa.CheckConstraint("request_hash ~ '^[0-9a-f]{64}$'", name="ck_case_snapshot_request_hash"),
        sa.CheckConstraint(
            "baseline_validity IN ('VALID','STALE','DISPUTED','MISSING','NOT_APPLICABLE')",
            name="ck_case_snapshot_baseline",
        ),
        *scope_fks(),
        sa.ForeignKeyConstraint(["case_id"], ["decision_case.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "snapshot_number", name="uq_case_snapshot_number"),
        sa.UniqueConstraint("case_id", "idempotency_key", name="uq_case_snapshot_idempotency"),
    )
    indexes("case_snapshot")
    op.create_index("ix_case_snapshot_case_id", "case_snapshot", ["case_id"])
    op.create_foreign_key(
        "fk_decision_case_last_snapshot",
        "decision_case",
        "case_snapshot",
        ["last_snapshot_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.create_table(
        "case_baseline_assessment",
        uid("id"),
        *scope(),
        uid("case_id"),
        uid("snapshot_id"),
        uid("authorized_context_id", True),
        sa.Column("validity", sa.String(30), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("assessed_by", sa.String(200), nullable=False),
        timestamp("assessed_at"),
        sa.CheckConstraint(
            "validity IN ('VALID','STALE','DISPUTED','MISSING','NOT_APPLICABLE')",
            name="ck_case_baseline_validity",
        ),
        *scope_fks(),
        sa.ForeignKeyConstraint(["case_id"], ["decision_case.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["case_snapshot.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["authorized_context_id"], ["authorized_context_version.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    indexes("case_baseline_assessment")
    op.create_index("ix_case_baseline_assessment_case_id", "case_baseline_assessment", ["case_id"])
    op.create_index(
        "ix_case_baseline_assessment_snapshot_id", "case_baseline_assessment", ["snapshot_id"]
    )

    op.create_table(
        "case_limitation",
        uid("id"),
        *scope(),
        uid("case_id"),
        uid("snapshot_id"),
        sa.Column("code", sa.String(60), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("material", sa.Boolean(), nullable=False),
        sa.Column("owner_actor_id", sa.String(200), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("resolved_by", sa.String(200), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        timestamp("created_at"),
        sa.CheckConstraint("status IN ('OPEN','RESOLVED')", name="ck_case_limitation_status"),
        sa.CheckConstraint(
            "(status = 'OPEN' AND resolution IS NULL AND resolved_by IS NULL "
            "AND resolved_at IS NULL) "
            "OR (status = 'RESOLVED' AND resolution IS NOT NULL AND resolved_by IS NOT NULL "
            "AND resolved_at IS NOT NULL)",
            name="ck_case_limitation_resolution",
        ),
        *scope_fks(),
        sa.ForeignKeyConstraint(["case_id"], ["decision_case.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["case_snapshot.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    indexes("case_limitation")
    op.create_index("ix_case_limitation_case_id", "case_limitation", ["case_id"])
    op.create_index("ix_case_limitation_snapshot_id", "case_limitation", ["snapshot_id"])

    op.create_table(
        "case_sufficiency_assessment",
        uid("id"),
        *scope(),
        uid("case_id"),
        uid("snapshot_id"),
        sa.Column("conclusion_type", sa.String(50), nullable=False),
        sa.Column("readiness", sa.String(50), nullable=False),
        sa.Column("present_evidence", jsonb, nullable=False),
        sa.Column("missing_evidence", jsonb, nullable=False),
        sa.Column("stale_evidence_ids", jsonb, nullable=False),
        sa.Column("weak_evidence_ids", jsonb, nullable=False),
        sa.Column("contradictory_evidence", jsonb, nullable=False),
        sa.Column("limitation_ids", jsonb, nullable=False),
        sa.Column("evidence_request_ids", jsonb, nullable=False),
        sa.Column("maximum_supported_conclusion", sa.String(80), nullable=False),
        sa.Column("policy_version", sa.String(40), nullable=False),
        sa.Column("assessed_by", sa.String(200), nullable=False),
        timestamp("assessed_at"),
        sa.CheckConstraint(
            "readiness IN ('DECISION_READY','DECISION_READY_WITH_LIMITATIONS',"
            "'VERIFICATION_REQUIRED','INSUFFICIENT')",
            name="ck_case_sufficiency_readiness",
        ),
        *scope_fks(),
        sa.ForeignKeyConstraint(["case_id"], ["decision_case.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["case_snapshot.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id", "conclusion_type", name="uq_snapshot_conclusion"),
    )
    indexes("case_sufficiency_assessment")
    op.create_index(
        "ix_case_sufficiency_assessment_case_id", "case_sufficiency_assessment", ["case_id"]
    )
    op.create_index(
        "ix_case_sufficiency_assessment_snapshot_id",
        "case_sufficiency_assessment",
        ["snapshot_id"],
    )

    op.create_table(
        "case_ledger_event",
        uid("id"),
        *scope(),
        uid("case_id"),
        sa.Column("case_version", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("from_lifecycle", sa.String(30), nullable=True),
        sa.Column("to_lifecycle", sa.String(30), nullable=True),
        sa.Column("actor_id", sa.String(200), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("details", jsonb, nullable=False),
        timestamp("occurred_at"),
        sa.CheckConstraint("case_version > 0", name="ck_case_ledger_version"),
        *scope_fks(),
        sa.ForeignKeyConstraint(["case_id"], ["decision_case.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    indexes("case_ledger_event")
    op.create_index("ix_case_ledger_event_case_id", "case_ledger_event", ["case_id"])

    op.execute(
        """
        INSERT INTO case_ledger_event
          (id, organization_id, project_id, case_id, case_version, event_type,
           from_lifecycle, to_lifecycle, actor_id, reason, details, occurred_at)
        SELECT gen_random_uuid(), organization_id, project_id, id, 1, 'CASE_OPENED',
               NULL, 'OPEN', created_by, 'Backfilled Phase 3 correlation opening',
               '{}'::jsonb, opened_at
        FROM decision_case;

        CREATE TRIGGER case_snapshot_append_only
          BEFORE UPDATE OR DELETE ON case_snapshot
          FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
        CREATE TRIGGER case_baseline_assessment_append_only
          BEFORE UPDATE OR DELETE ON case_baseline_assessment
          FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
        CREATE TRIGGER case_sufficiency_assessment_append_only
          BEFORE UPDATE OR DELETE ON case_sufficiency_assessment
          FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
        CREATE TRIGGER case_ledger_event_append_only
          BEFORE UPDATE OR DELETE ON case_ledger_event
          FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
        CREATE TRIGGER case_active_response_append_only
          BEFORE UPDATE OR DELETE ON case_active_response
          FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
        CREATE TRIGGER case_evidence_attachment_append_only
          BEFORE UPDATE OR DELETE ON case_evidence_attachment
          FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();

        CREATE FUNCTION protect_case_limitation_change() RETURNS trigger AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'case limitation records cannot be deleted';
          END IF;
          IF ROW(NEW.id, NEW.organization_id, NEW.project_id, NEW.case_id, NEW.snapshot_id,
                 NEW.code, NEW.description, NEW.material, NEW.owner_actor_id, NEW.due_at,
                 NEW.created_at)
             IS DISTINCT FROM
             ROW(OLD.id, OLD.organization_id, OLD.project_id, OLD.case_id, OLD.snapshot_id,
                 OLD.code, OLD.description, OLD.material, OLD.owner_actor_id, OLD.due_at,
                 OLD.created_at)
             OR OLD.status <> 'OPEN' OR NEW.status <> 'RESOLVED'
             OR NEW.resolution IS NULL OR NEW.resolved_by IS NULL OR NEW.resolved_at IS NULL
          THEN
            RAISE EXCEPTION 'case limitations only allow one recorded resolution';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER case_limitation_protected
          BEFORE UPDATE OR DELETE ON case_limitation
          FOR EACH ROW EXECUTE FUNCTION protect_case_limitation_change();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER case_limitation_protected ON case_limitation")
    op.execute("DROP FUNCTION protect_case_limitation_change()")
    op.execute("DROP TRIGGER case_evidence_attachment_append_only ON case_evidence_attachment")
    op.execute("DROP TRIGGER case_active_response_append_only ON case_active_response")
    op.execute("DROP TRIGGER case_ledger_event_append_only ON case_ledger_event")
    op.execute(
        "DROP TRIGGER case_sufficiency_assessment_append_only ON case_sufficiency_assessment"
    )
    op.execute("DROP TRIGGER case_baseline_assessment_append_only ON case_baseline_assessment")
    op.execute("DROP TRIGGER case_snapshot_append_only ON case_snapshot")
    op.drop_constraint("fk_decision_case_last_snapshot", "decision_case", type_="foreignkey")
    for table in (
        "case_ledger_event",
        "case_sufficiency_assessment",
        "case_limitation",
        "case_baseline_assessment",
        "case_snapshot",
        "case_active_response",
        "case_evidence_attachment",
    ):
        op.drop_table(table)
    op.drop_constraint("ck_decision_case_close_basis", "decision_case", type_="check")
    op.drop_constraint("ck_decision_case_reopen_trigger", "decision_case", type_="check")
    op.drop_constraint("ck_decision_case_autonomy_class", "decision_case", type_="check")
    op.drop_constraint("ck_decision_case_governance_state", "decision_case", type_="check")
    op.drop_constraint("ck_decision_case_readiness", "decision_case", type_="check")
    op.drop_constraint("ck_decision_case_lifecycle", "decision_case", type_="check")
    for name in (
        "reopened_at",
        "reopen_reason",
        "reopen_trigger",
        "closed_at",
        "close_reason",
        "outcome_reference",
        "last_snapshot_id",
        "blocker_description",
        "blocker_code",
        "blocked_from_lifecycle",
        "autonomy_class",
        "governance_state",
        "readiness",
    ):
        op.drop_column("decision_case", name)
    op.create_check_constraint("ck_case_shell_lifecycle", "decision_case", "lifecycle = 'OPEN'")
