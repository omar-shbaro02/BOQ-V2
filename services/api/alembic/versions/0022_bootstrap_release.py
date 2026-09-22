"""Add reviewed and authorized bootstrap schedule releases."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0022_bootstrap_release"
down_revision: str | None = "0021_bootstrap_cpm"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "bootstrap_schedule_release",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(), nullable=False),
        sa.Column("project_id", postgresql.UUID(), nullable=False),
        sa.Column("calculation_id", postgresql.UUID(), nullable=False),
        sa.Column("supersedes_release_id", postgresql.UUID()),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(40), nullable=False),
        sa.Column("schedule_payload", jsonb, nullable=False),
        sa.Column("edit_history", jsonb, nullable=False),
        sa.Column("review_reason", sa.Text(), nullable=False),
        sa.Column("authority_grant_id", postgresql.UUID()),
        sa.Column("authorized_context_id", postgresql.UUID()),
        sa.Column("approval_reference", sa.Text()),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["calculation_id"], ["bootstrap_schedule_calculation.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_release_id"], ["bootstrap_schedule_release.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["authority_grant_id"], ["authority_grant.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["authorized_context_id"], ["authorized_context_version.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "calculation_id", "version_number", name="uq_bootstrap_release_version"
        ),
        sa.UniqueConstraint("project_id", "idempotency_key", name="uq_bootstrap_release_idem"),
    )
    for column in ("organization_id", "project_id", "calculation_id", "supersedes_release_id"):
        op.create_index(
            f"ix_bootstrap_schedule_release_{column}", "bootstrap_schedule_release", [column]
        )
    op.execute("""
        CREATE TRIGGER bootstrap_schedule_release_append_only
        BEFORE UPDATE OR DELETE ON bootstrap_schedule_release
        FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER bootstrap_schedule_release_append_only ON bootstrap_schedule_release")
    op.drop_table("bootstrap_schedule_release")
