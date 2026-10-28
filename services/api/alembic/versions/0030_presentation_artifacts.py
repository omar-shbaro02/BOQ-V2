"""Add immutable report-derived presentations and human approval history."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0030_presentation_artifacts"
down_revision: str | None = "0029_snapshot_health"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid = postgresql.UUID()
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "presentation_artifact",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("report_snapshot_id", uuid, nullable=False),
        sa.Column("source_report_approval_event_id", uuid, nullable=False),
        sa.Column("source_report_hash", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("generator_version", sa.String(60), nullable=False),
        sa.Column("recipients", jsonb, nullable=False),
        sa.Column("fidelity_manifest", jsonb, nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("generated_by", sa.String(200), nullable=False),
        sa.Column(
            "generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["report_snapshot_id"], ["report_snapshot.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_report_approval_event_id"], ["report_lifecycle_event.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("project_id", "idempotency_key", name="uq_presentation_idem"),
    )
    op.create_table(
        "presentation_lifecycle_event",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("presentation_id", uuid, nullable=False),
        sa.Column("event_number", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.String(20)),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("authority_grant_id", uuid),
        sa.Column("actor_id", sa.String(200), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["presentation_id"], ["presentation_artifact.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["authority_grant_id"], ["authority_grant.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("presentation_id", "event_number", name="uq_presentation_event_no"),
        sa.UniqueConstraint("project_id", "idempotency_key", name="uq_presentation_event_idem"),
        sa.CheckConstraint("event_number > 0", name="ck_presentation_event_no"),
        sa.CheckConstraint(
            "to_status IN ('DRAFT','REVIEWED','APPROVED')", name="ck_presentation_event_status"
        ),
    )
    for table, extra in (
        ("presentation_artifact", "report_snapshot_id"),
        ("presentation_lifecycle_event", "presentation_id"),
    ):
        for column in ("organization_id", "project_id", extra):
            op.create_index(f"ix_{table}_{column}", table, [column])
        op.execute(
            f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION reject_append_only_change()"
        )


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM presentation_artifact)")):
        raise RuntimeError(
            "Cannot drop immutable presentation history; "
            "retain schema or restore an authorized backup"
        )
    op.drop_table("presentation_lifecycle_event")
    op.drop_table("presentation_artifact")
