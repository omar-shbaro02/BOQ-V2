"""Persist immutable evidence-backed progress workbook imports."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0028_progress_workbook_imports"
down_revision: str | None = "0027_project_context_records"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid = postgresql.UUID()
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "progress_workbook_import",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("artifact_id", uuid, nullable=False),
        sa.Column("schedule_context_id", uuid, nullable=False),
        sa.Column("data_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rows", jsonb, nullable=False),
        sa.Column("network_basis", jsonb, nullable=False),
        sa.Column("limitations", jsonb, nullable=False),
        sa.Column("formula_version", sa.String(60), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("recorded_by", sa.String(200), nullable=False),
        sa.Column(
            "recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["artifact_id"], ["evidence_artifact.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["schedule_context_id"], ["authorized_context_version.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("project_id", "idempotency_key", name="uq_progress_workbook_idem"),
        sa.UniqueConstraint(
            "project_id",
            "artifact_id",
            "schedule_context_id",
            "data_date",
            name="uq_progress_workbook_source",
        ),
    )
    for column in ("organization_id", "project_id"):
        op.create_index(
            f"ix_progress_workbook_import_{column}", "progress_workbook_import", [column]
        )
    op.execute(
        "CREATE TRIGGER progress_workbook_import_append_only "
        "BEFORE UPDATE OR DELETE ON progress_workbook_import "
        "FOR EACH ROW EXECUTE FUNCTION reject_append_only_change()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER progress_workbook_import_append_only ON progress_workbook_import")
    op.drop_table("progress_workbook_import")
