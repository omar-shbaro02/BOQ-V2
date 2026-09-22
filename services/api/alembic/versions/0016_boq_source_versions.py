"""Add immutable BOQ source versions and extracted raw rows."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016_boq_source_versions"
down_revision: str | None = "0015_learning_records"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "boq_source_version",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(),
            sa.ForeignKey("organization.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(),
            sa.ForeignKey("project.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "artifact_id",
            postgresql.UUID(),
            sa.ForeignKey("evidence_artifact.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "prior_source_version_id",
            postgresql.UUID(),
            sa.ForeignKey("boq_source_version.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("source_format", sa.String(20), nullable=False),
        sa.Column("parser_name", sa.String(80), nullable=False),
        sa.Column("parser_version", sa.String(40), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("extraction_status", sa.String(40), nullable=False),
        sa.Column("extraction_confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("structure_manifest", jsonb, nullable=False),
        sa.Column("warnings", jsonb, nullable=False),
        sa.Column("extracted_row_count", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("version_number > 0", name="ck_boq_source_version_positive"),
        sa.CheckConstraint("extracted_row_count >= 0", name="ck_boq_source_row_count"),
        sa.CheckConstraint(
            "extraction_confidence BETWEEN 0 AND 1", name="ck_boq_source_confidence"
        ),
        sa.CheckConstraint(
            "extraction_status IN ('RECEIVED', 'EXTRACTED', 'VERIFICATION_REQUIRED', 'FAILED')",
            name="ck_boq_source_extraction_status",
        ),
        sa.UniqueConstraint("project_id", "version_number", name="uq_boq_source_project_version"),
        sa.UniqueConstraint("project_id", "artifact_id", name="uq_boq_source_project_artifact"),
        sa.UniqueConstraint("project_id", "idempotency_key", name="uq_boq_source_idempotency"),
    )
    for column in ("organization_id", "project_id", "artifact_id", "prior_source_version_id"):
        op.create_index(f"ix_boq_source_version_{column}", "boq_source_version", [column])

    op.create_table(
        "boq_source_row",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(),
            sa.ForeignKey("organization.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(),
            sa.ForeignKey("project.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "source_version_id",
            postgresql.UUID(),
            sa.ForeignKey("boq_source_version.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("sheet_name", sa.String(200), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("row_number", sa.Integer(), nullable=True),
        sa.Column("region", jsonb, nullable=True),
        sa.Column("raw_values", jsonb, nullable=False),
        sa.Column("original_text", sa.Text(), nullable=True),
        sa.Column("extraction_confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("warnings", jsonb, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("sequence_number > 0", name="ck_boq_row_sequence_positive"),
        sa.CheckConstraint("row_number IS NULL OR row_number > 0", name="ck_boq_row_number"),
        sa.CheckConstraint("page_number IS NULL OR page_number > 0", name="ck_boq_page_number"),
        sa.CheckConstraint("extraction_confidence BETWEEN 0 AND 1", name="ck_boq_row_confidence"),
        sa.UniqueConstraint("source_version_id", "sequence_number", name="uq_boq_row_sequence"),
    )
    for column in ("organization_id", "project_id", "source_version_id"):
        op.create_index(f"ix_boq_source_row_{column}", "boq_source_row", [column])

    op.execute("""
        CREATE TRIGGER boq_source_version_append_only
        BEFORE UPDATE OR DELETE ON boq_source_version
        FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
    """)
    op.execute("""
        CREATE TRIGGER boq_source_row_append_only
        BEFORE UPDATE OR DELETE ON boq_source_row
        FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER boq_source_row_append_only ON boq_source_row")
    op.execute("DROP TRIGGER boq_source_version_append_only ON boq_source_version")
    op.drop_table("boq_source_row")
    op.drop_table("boq_source_version")
