"""Add immutable BOQ normalization runs and canonical lines."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017_boq_normalization"
down_revision: str | None = "0016_boq_source_versions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "boq_normalization_run",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(), nullable=False),
        sa.Column("project_id", postgresql.UUID(), nullable=False),
        sa.Column("source_version_id", postgresql.UUID(), nullable=False),
        sa.Column("normalizer_version", sa.String(40), nullable=False),
        sa.Column("header_rows", jsonb, nullable=False),
        sa.Column("column_mapping", jsonb, nullable=False),
        sa.Column("warnings", jsonb, nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("schedule_relevant_rows", sa.Integer(), nullable=False),
        sa.Column("review_required_rows", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["source_version_id"], ["boq_source_version.id"], ondelete="RESTRICT"
        ),
        sa.CheckConstraint("total_rows >= 0", name="ck_boq_normalization_total"),
        sa.CheckConstraint(
            "schedule_relevant_rows BETWEEN 0 AND total_rows",
            name="ck_boq_normalization_relevant",
        ),
        sa.CheckConstraint(
            "review_required_rows BETWEEN 0 AND total_rows",
            name="ck_boq_normalization_review",
        ),
        sa.UniqueConstraint("source_version_id", name="uq_boq_normalization_source"),
        sa.UniqueConstraint(
            "project_id", "idempotency_key", name="uq_boq_normalization_idempotency"
        ),
    )
    for column in ("organization_id", "project_id", "source_version_id"):
        op.create_index(f"ix_boq_normalization_run_{column}", "boq_normalization_run", [column])

    op.create_table(
        "boq_line",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column("stable_line_id", sa.String(80), nullable=False),
        sa.Column("organization_id", postgresql.UUID(), nullable=False),
        sa.Column("project_id", postgresql.UUID(), nullable=False),
        sa.Column("normalization_run_id", postgresql.UUID(), nullable=False),
        sa.Column("source_version_id", postgresql.UUID(), nullable=False),
        sa.Column("source_row_id", postgresql.UUID(), nullable=False),
        sa.Column("source_location", jsonb, nullable=False),
        sa.Column("item_number", sa.String(160), nullable=True),
        sa.Column("division", sa.String(240), nullable=True),
        sa.Column("source_wbs_code", sa.String(160), nullable=True),
        sa.Column("item_name", sa.String(300), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("unit", sa.String(80), nullable=True),
        sa.Column("quantity", sa.Numeric(24, 6), nullable=True),
        sa.Column("unit_price", sa.Numeric(24, 6), nullable=True),
        sa.Column("total_price", sa.Numeric(24, 6), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("location", sa.String(240), nullable=True),
        sa.Column("trade", sa.String(160), nullable=True),
        sa.Column("package", sa.String(240), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("parent_section", sa.String(300), nullable=True),
        sa.Column("source_row_text", sa.Text(), nullable=True),
        sa.Column("normalized_values", jsonb, nullable=False),
        sa.Column("unmapped_values", jsonb, nullable=False),
        sa.Column("classification", sa.String(60), nullable=False),
        sa.Column("classification_basis", jsonb, nullable=False),
        sa.Column("schedule_relevant", sa.Boolean(), nullable=False),
        sa.Column("confidence", sa.String(20), nullable=False),
        sa.Column("review_state", sa.String(30), nullable=False),
        sa.Column("warnings", jsonb, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["normalization_run_id"], ["boq_normalization_run.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_version_id"], ["boq_source_version.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["source_row_id"], ["boq_source_row.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "currency IS NULL OR currency ~ '^[A-Z]{3}$'", name="ck_boq_line_currency"
        ),
        sa.CheckConstraint(
            "classification IN ('DIRECT_EXECUTION_SCOPE','PROCUREMENT_OR_SUPPLY',"
            "'TESTING_COMMISSIONING','APPROVAL_INSPECTION','PRELIMINARIES_GENERAL',"
            "'SUMMARY_HEADER','SUBTOTAL_TOTAL','PROVISIONAL_OR_ALLOWANCE',"
            "'MATERIAL_ONLY_NON_SCHEDULE','UNKNOWN_REVIEW_REQUIRED')",
            name="ck_boq_line_classification",
        ),
        sa.CheckConstraint(
            "confidence IN ('HIGH','MEDIUM','LOW','INSUFFICIENT')",
            name="ck_boq_line_confidence",
        ),
        sa.CheckConstraint(
            "review_state IN ('NOT_REVIEWED','REVIEW_REQUIRED','ACCEPTED','REVISED','REJECTED')",
            name="ck_boq_line_review_state",
        ),
        sa.UniqueConstraint("normalization_run_id", "source_row_id", name="uq_boq_line_source_row"),
        sa.UniqueConstraint("source_version_id", "stable_line_id", name="uq_boq_stable_line"),
    )
    for column in (
        "organization_id",
        "project_id",
        "normalization_run_id",
        "source_version_id",
        "source_row_id",
    ):
        op.create_index(f"ix_boq_line_{column}", "boq_line", [column])

    for table in ("boq_normalization_run", "boq_line"):
        op.execute(f"""
            CREATE TRIGGER {table}_append_only
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
        """)


def downgrade() -> None:
    op.execute("DROP TRIGGER boq_line_append_only ON boq_line")
    op.execute("DROP TRIGGER boq_normalization_run_append_only ON boq_normalization_run")
    op.drop_table("boq_line")
    op.drop_table("boq_normalization_run")
