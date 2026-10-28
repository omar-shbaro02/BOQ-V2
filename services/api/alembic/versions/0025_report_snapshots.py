"""Add immutable governed report snapshots and lifecycle events."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0025_report_snapshots"
down_revision: str | None = "0024_project_control_snapshots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "report_snapshot",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(), nullable=False),
        sa.Column("project_id", postgresql.UUID(), nullable=False),
        sa.Column("project_control_snapshot_id", postgresql.UUID(), nullable=False),
        sa.Column("case_id", postgresql.UUID()),
        sa.Column("report_number", sa.Integer(), nullable=False),
        sa.Column("report_type", sa.String(50), nullable=False),
        sa.Column("schema_version", sa.String(40), nullable=False),
        sa.Column("report_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", jsonb, nullable=False),
        sa.Column("source_refs", jsonb, nullable=False),
        sa.Column("policy_versions", jsonb, nullable=False),
        sa.Column("generator_version", sa.String(40), nullable=False),
        sa.Column("semantic_notice", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("fidelity_manifest", jsonb, nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("generated_by", sa.String(200), nullable=False),
        sa.Column(
            "generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["project_control_snapshot_id"], ["project_control_snapshot.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["case_id"], ["decision_case.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("project_id", "report_number", name="uq_report_snapshot_no"),
        sa.UniqueConstraint("project_id", "idempotency_key", name="uq_report_snapshot_idem"),
    )
    op.create_table(
        "report_lifecycle_event",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(), nullable=False),
        sa.Column("project_id", postgresql.UUID(), nullable=False),
        sa.Column("report_snapshot_id", postgresql.UUID(), nullable=False),
        sa.Column("event_number", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.String(20)),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("authority_grant_id", postgresql.UUID()),
        sa.Column("actor_id", sa.String(200), nullable=False),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "to_status IN ('DRAFT','REVIEWED','APPROVED')", name="ck_report_event_status"
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["report_snapshot_id"], ["report_snapshot.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["authority_grant_id"], ["authority_grant.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("report_snapshot_id", "event_number", name="uq_report_event_no"),
    )
    for table in ("report_snapshot", "report_lifecycle_event"):
        op.create_index(f"ix_{table}_organization_id", table, ["organization_id"])
        op.create_index(f"ix_{table}_project_id", table, ["project_id"])
    op.create_index(
        "ix_report_snapshot_project_control_snapshot_id",
        "report_snapshot",
        ["project_control_snapshot_id"],
    )
    op.create_index("ix_report_snapshot_case_id", "report_snapshot", ["case_id"])
    op.create_index(
        "ix_report_lifecycle_event_report_snapshot_id",
        "report_lifecycle_event",
        ["report_snapshot_id"],
    )
    op.execute("""
        CREATE TRIGGER report_snapshot_append_only BEFORE UPDATE OR DELETE ON report_snapshot
        FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
        CREATE TRIGGER report_lifecycle_event_append_only
        BEFORE UPDATE OR DELETE ON report_lifecycle_event
        FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER report_lifecycle_event_append_only ON report_lifecycle_event")
    op.execute("DROP TRIGGER report_snapshot_append_only ON report_snapshot")
    op.drop_table("report_lifecycle_event")
    op.drop_table("report_snapshot")
