"""Add immutable project context versions and append-only lifecycle commands."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0027_project_context_records"
down_revision: str | None = "0026_boq_activity_allocations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid = postgresql.UUID()
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "project_context_record",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("record_type", sa.String(30), nullable=False),
        sa.Column("record_key", sa.String(120), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("supersedes_record_id", uuid),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("initial_status", sa.String(30), nullable=False),
        sa.Column("payload", jsonb, nullable=False),
        sa.Column("evidence_item_ids", jsonb, nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["supersedes_record_id"], ["project_context_record.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "project_id",
            "record_type",
            "record_key",
            "version_number",
            name="uq_project_context_record_version",
        ),
        sa.UniqueConstraint("project_id", "idempotency_key", name="uq_project_context_record_idem"),
        sa.CheckConstraint("version_number > 0", name="ck_project_context_version_positive"),
        sa.CheckConstraint(
            "record_type IN ('CHARTER','STAKEHOLDER','DAILY_UPDATE',"
            "'RISK','ISSUE','CHANGE_REQUEST')",
            name="ck_project_context_type",
        ),
    )
    op.create_table(
        "project_context_lifecycle_event",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("record_id", uuid, nullable=False),
        sa.Column("event_number", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.String(30)),
        sa.Column("to_status", sa.String(30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("authority_grant_id", uuid),
        sa.Column("authorized_context_id", uuid),
        sa.Column("actor_id", sa.String(200), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["record_id"], ["project_context_record.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["authority_grant_id"], ["authority_grant.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["authorized_context_id"], ["authorized_context_version.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("record_id", "event_number", name="uq_project_context_event_no"),
        sa.UniqueConstraint("project_id", "idempotency_key", name="uq_project_context_event_idem"),
        sa.CheckConstraint("event_number > 0", name="ck_project_context_event_positive"),
    )
    for table in ("project_context_record", "project_context_lifecycle_event"):
        for column in ("organization_id", "project_id"):
            op.create_index(f"ix_{table}_{column}", table, [column])
        op.execute(
            f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION reject_append_only_change()"
        )
    op.create_index(
        "ix_project_context_record_record_type", "project_context_record", ["record_type"]
    )
    op.create_index(
        "ix_project_context_lifecycle_event_record_id",
        "project_context_lifecycle_event",
        ["record_id"],
    )


def downgrade() -> None:
    for table in ("project_context_lifecycle_event", "project_context_record"):
        op.execute(f"DROP TRIGGER {table}_append_only ON {table}")
        op.drop_table(table)
