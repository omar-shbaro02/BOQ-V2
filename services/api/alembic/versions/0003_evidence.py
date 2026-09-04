"""Create Phase 2 governed evidence and import tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_evidence"
down_revision: str | None = "0002_control_context"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def uuid_column(name: str, *, nullable: bool = False) -> sa.Column:
    return sa.Column(name, postgresql.UUID(as_uuid=True), nullable=nullable)


def created_at_column(name: str = "created_at") -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def scope_columns() -> tuple[sa.Column, sa.Column]:
    return uuid_column("organization_id"), uuid_column("project_id")


def scope_constraints() -> tuple[sa.ForeignKeyConstraint, sa.ForeignKeyConstraint]:
    return (
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="RESTRICT"),
    )


def add_scope_indexes(table: str) -> None:
    op.create_index(f"ix_{table}_organization_id", table, ["organization_id"])
    op.create_index(f"ix_{table}_project_id", table, ["project_id"])


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "evidence_artifact",
        uuid_column("id"),
        *scope_columns(),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("media_type", sa.String(150), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("source_type", sa.String(80), nullable=False),
        sa.Column("source_id", sa.String(200), nullable=False),
        sa.Column("provided_by_actor", sa.String(200), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        created_at_column("received_at"),
        sa.Column("classification", sa.String(30), nullable=False),
        sa.Column("parser_version", sa.String(80), nullable=True),
        sa.Column("scan_result", sa.String(20), nullable=False),
        sa.Column("scan_engine", sa.String(80), nullable=False),
        sa.Column("scan_signature_version", sa.String(80), nullable=False),
        sa.Column("scanned_at", sa.DateTime(timezone=True), nullable=False),
        uuid_column("supersedes_artifact_id", nullable=True),
        sa.CheckConstraint("size_bytes >= 0", name="ck_artifact_size"),
        sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="ck_artifact_sha256"),
        sa.CheckConstraint(
            "classification IN ('PUBLIC', 'INTERNAL', 'CONFIDENTIAL', 'RESTRICTED')",
            name="ck_artifact_classification",
        ),
        sa.CheckConstraint("scan_result = 'CLEAN'", name="ck_artifact_scan_result"),
        *scope_constraints(),
        sa.ForeignKeyConstraint(
            ["supersedes_artifact_id"], ["evidence_artifact.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    add_scope_indexes("evidence_artifact")
    op.create_index("ix_evidence_artifact_sha256", "evidence_artifact", ["sha256"])

    op.create_table(
        "evidence_item",
        uuid_column("id"),
        *scope_columns(),
        uuid_column("artifact_id", nullable=True),
        uuid_column("controlled_object_id", nullable=True),
        sa.Column("field_name", sa.String(120), nullable=False),
        sa.Column("value", jsonb, nullable=False),
        sa.Column("unit", sa.String(30), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("measurement_basis", sa.String(80), nullable=True),
        sa.Column("semantic_state", sa.String(30), nullable=False),
        sa.Column("truth_type", sa.String(30), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("source_reliability", sa.Numeric(5, 4), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        uuid_column("supersedes_item_id", nullable=True),
        uuid_column("derived_from_item_id", nullable=True),
        sa.Column("created_by", sa.String(200), nullable=False),
        created_at_column(),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_evidence_confidence"),
        sa.CheckConstraint(
            "source_reliability IS NULL OR source_reliability BETWEEN 0 AND 1",
            name="ck_evidence_source_reliability",
        ),
        sa.CheckConstraint(
            "currency IS NULL OR currency ~ '^[A-Z]{3}$'", name="ck_evidence_currency"
        ),
        sa.CheckConstraint("expires_at IS NULL OR expires_at > as_of", name="ck_evidence_expiry"),
        sa.CheckConstraint("status IN ('ACTIVE', 'SUPERSEDED')", name="ck_evidence_status"),
        sa.CheckConstraint(
            "(value <> 'null'::jsonb) OR truth_type = 'UNKNOWN'",
            name="ck_evidence_null_unknown",
        ),
        *scope_constraints(),
        sa.ForeignKeyConstraint(["artifact_id"], ["evidence_artifact.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["controlled_object_id"], ["controlled_object.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["supersedes_item_id"], ["evidence_item.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["derived_from_item_id"], ["evidence_item.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    add_scope_indexes("evidence_item")
    for column in ("artifact_id", "controlled_object_id", "field_name"):
        op.create_index(f"ix_evidence_item_{column}", "evidence_item", [column])

    op.create_table(
        "evidence_relation",
        uuid_column("id"),
        *scope_columns(),
        uuid_column("from_item_id"),
        uuid_column("to_item_id"),
        sa.Column("relation_type", sa.String(30), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        created_at_column(),
        sa.CheckConstraint("from_item_id <> to_item_id", name="ck_evidence_relation_not_self"),
        sa.CheckConstraint(
            "relation_type IN ('SUPPORTS', 'CONTRADICTS', 'DERIVED_FROM')",
            name="ck_evidence_relation_type",
        ),
        *scope_constraints(),
        sa.ForeignKeyConstraint(["from_item_id"], ["evidence_item.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_item_id"], ["evidence_item.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "from_item_id", "to_item_id", "relation_type", name="uq_evidence_relation"
        ),
    )
    add_scope_indexes("evidence_relation")
    op.create_index("ix_evidence_relation_from_item_id", "evidence_relation", ["from_item_id"])
    op.create_index("ix_evidence_relation_to_item_id", "evidence_relation", ["to_item_id"])

    op.create_table(
        "verification_event",
        uuid_column("id"),
        *scope_columns(),
        uuid_column("evidence_item_id"),
        uuid_column("result_item_id", nullable=True),
        sa.Column("method", sa.String(160), nullable=False),
        sa.Column("outcome", sa.String(30), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("reviewer_actor_id", sa.String(200), nullable=False),
        created_at_column("occurred_at"),
        sa.CheckConstraint(
            "outcome IN ('VERIFIED', 'REJECTED', 'PARTIALLY_VERIFIED', 'UNABLE')",
            name="ck_verification_outcome",
        ),
        *scope_constraints(),
        sa.ForeignKeyConstraint(["evidence_item_id"], ["evidence_item.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["result_item_id"], ["evidence_item.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    add_scope_indexes("verification_event")
    op.create_index(
        "ix_verification_event_evidence_item_id", "verification_event", ["evidence_item_id"]
    )

    op.create_table(
        "source_reliability_assessment",
        uuid_column("id"),
        *scope_columns(),
        sa.Column("source_type", sa.String(80), nullable=False),
        sa.Column("source_id", sa.String(200), nullable=False),
        sa.Column("evidence_class", sa.String(80), nullable=False),
        sa.Column("score", sa.Numeric(5, 4), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("assessed_by", sa.String(200), nullable=False),
        created_at_column(),
        sa.CheckConstraint("score BETWEEN 0 AND 1", name="ck_reliability_score"),
        *scope_constraints(),
        sa.PrimaryKeyConstraint("id"),
    )
    add_scope_indexes("source_reliability_assessment")
    op.create_index(
        "ix_source_reliability_lookup",
        "source_reliability_assessment",
        ["project_id", "source_type", "source_id", "valid_from"],
    )

    op.create_table(
        "contradiction",
        uuid_column("id"),
        *scope_columns(),
        uuid_column("controlled_object_id", nullable=True),
        uuid_column("left_item_id"),
        uuid_column("right_item_id"),
        sa.Column("field_name", sa.String(120), nullable=False),
        sa.Column("material", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("resolution_policy", sa.String(120), nullable=True),
        uuid_column("chosen_item_id", nullable=True),
        sa.Column("resolution_reason", sa.Text(), nullable=True),
        sa.Column("resolved_by", sa.String(200), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(200), nullable=False),
        created_at_column(),
        sa.CheckConstraint("left_item_id <> right_item_id", name="ck_contradiction_distinct"),
        sa.CheckConstraint("status IN ('OPEN', 'RESOLVED')", name="ck_contradiction_status"),
        sa.CheckConstraint(
            "chosen_item_id IS NULL OR chosen_item_id IN (left_item_id, right_item_id)",
            name="ck_contradiction_choice",
        ),
        *scope_constraints(),
        sa.ForeignKeyConstraint(
            ["controlled_object_id"], ["controlled_object.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["left_item_id"], ["evidence_item.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["right_item_id"], ["evidence_item.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["chosen_item_id"], ["evidence_item.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    add_scope_indexes("contradiction")
    op.create_index(
        "ix_contradiction_controlled_object_id", "contradiction", ["controlled_object_id"]
    )

    op.create_table(
        "evidence_request",
        uuid_column("id"),
        *scope_columns(),
        uuid_column("controlled_object_id", nullable=True),
        sa.Column("requested_fields", jsonb, nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("urgency", sa.String(20), nullable=False),
        sa.Column("owner_actor_id", sa.String(200), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        uuid_column("satisfied_by_item_id", nullable=True),
        sa.Column("created_by", sa.String(200), nullable=False),
        created_at_column(),
        sa.CheckConstraint(
            "urgency IN ('NONE', 'ROUTINE', 'ELEVATED', 'URGENT', 'IMMEDIATE')",
            name="ck_evidence_request_urgency",
        ),
        sa.CheckConstraint(
            "status IN ('OPEN', 'SATISFIED', 'CANCELLED')", name="ck_evidence_request_status"
        ),
        *scope_constraints(),
        sa.ForeignKeyConstraint(
            ["controlled_object_id"], ["controlled_object.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["satisfied_by_item_id"], ["evidence_item.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    add_scope_indexes("evidence_request")
    op.create_index(
        "ix_evidence_request_controlled_object_id", "evidence_request", ["controlled_object_id"]
    )

    op.create_table(
        "import_batch",
        uuid_column("id"),
        *scope_columns(),
        uuid_column("artifact_id"),
        sa.Column("import_format", sa.String(10), nullable=False),
        sa.Column("mapping", jsonb, nullable=False),
        sa.Column("normalized_rows", jsonb, nullable=False),
        sa.Column("validation_errors", jsonb, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("valid_rows", sa.Integer(), nullable=False),
        sa.Column("rejected_rows", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        created_at_column(),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('PREVIEW', 'COMMITTED', 'REJECTED')", name="ck_import_batch_status"
        ),
        sa.CheckConstraint(
            "total_rows >= 0 AND valid_rows >= 0 AND rejected_rows >= 0",
            name="ck_import_batch_counts",
        ),
        *scope_constraints(),
        sa.ForeignKeyConstraint(["artifact_id"], ["evidence_artifact.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "idempotency_key", name="uq_import_batch_idempotency"),
    )
    add_scope_indexes("import_batch")
    op.create_index("ix_import_batch_artifact_id", "import_batch", ["artifact_id"])

    op.create_table(
        "import_batch_item",
        uuid_column("batch_id"),
        uuid_column("evidence_item_id"),
        sa.ForeignKeyConstraint(["batch_id"], ["import_batch.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evidence_item_id"], ["evidence_item.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("batch_id", "evidence_item_id"),
    )

    op.execute(
        """
        CREATE FUNCTION reject_append_only_change() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql;

        CREATE FUNCTION protect_evidence_item_assertion() RETURNS trigger AS $$
        BEGIN
          IF ROW(NEW.organization_id, NEW.project_id, NEW.artifact_id,
                 NEW.controlled_object_id, NEW.field_name, NEW.value, NEW.unit,
                 NEW.currency, NEW.measurement_basis, NEW.semantic_state, NEW.truth_type,
                 NEW.as_of, NEW.expires_at, NEW.confidence, NEW.source_reliability,
                 NEW.supersedes_item_id, NEW.derived_from_item_id, NEW.created_by, NEW.created_at)
             IS DISTINCT FROM
             ROW(OLD.organization_id, OLD.project_id, OLD.artifact_id,
                 OLD.controlled_object_id, OLD.field_name, OLD.value, OLD.unit,
                 OLD.currency, OLD.measurement_basis, OLD.semantic_state, OLD.truth_type,
                 OLD.as_of, OLD.expires_at, OLD.confidence, OLD.source_reliability,
                 OLD.supersedes_item_id, OLD.derived_from_item_id, OLD.created_by, OLD.created_at)
          THEN
            RAISE EXCEPTION 'evidence assertion fields are immutable';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER evidence_artifact_append_only
          BEFORE UPDATE OR DELETE ON evidence_artifact
          FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
        CREATE TRIGGER verification_event_append_only
          BEFORE UPDATE OR DELETE ON verification_event
          FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
        CREATE TRIGGER source_reliability_append_only
          BEFORE UPDATE OR DELETE ON source_reliability_assessment
          FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
        CREATE TRIGGER evidence_item_assertion_immutable
          BEFORE UPDATE ON evidence_item
          FOR EACH ROW EXECUTE FUNCTION protect_evidence_item_assertion();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER evidence_item_assertion_immutable ON evidence_item")
    op.execute("DROP TRIGGER source_reliability_append_only ON source_reliability_assessment")
    op.execute("DROP TRIGGER verification_event_append_only ON verification_event")
    op.execute("DROP TRIGGER evidence_artifact_append_only ON evidence_artifact")
    op.execute("DROP FUNCTION protect_evidence_item_assertion()")
    op.execute("DROP FUNCTION reject_append_only_change()")
    for table in (
        "import_batch_item",
        "import_batch",
        "evidence_request",
        "contradiction",
        "source_reliability_assessment",
        "verification_event",
        "evidence_relation",
        "evidence_item",
        "evidence_artifact",
    ):
        op.drop_table(table)
