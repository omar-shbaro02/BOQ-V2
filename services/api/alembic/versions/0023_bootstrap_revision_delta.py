"""Add immutable BOQ revision schedule deltas."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0023_bootstrap_revision_delta"
down_revision: str | None = "0022_bootstrap_release"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "bootstrap_revision_delta",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(), nullable=False),
        sa.Column("project_id", postgresql.UUID(), nullable=False),
        sa.Column("prior_source_version_id", postgresql.UUID(), nullable=False),
        sa.Column("new_source_version_id", postgresql.UUID(), nullable=False),
        sa.Column("prior_release_id", postgresql.UUID()),
        sa.Column("comparison_version", sa.String(40), nullable=False),
        sa.Column("added_scope", jsonb, nullable=False),
        sa.Column("removed_scope", jsonb, nullable=False),
        sa.Column("changed_scope", jsonb, nullable=False),
        sa.Column("mapping_changes", jsonb, nullable=False),
        sa.Column("activity_changes", jsonb, nullable=False),
        sa.Column("schedule_effects", jsonb, nullable=False),
        sa.Column("current_authorized_context_id", postgresql.UUID()),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["prior_source_version_id"], ["boq_source_version.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["new_source_version_id"], ["boq_source_version.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["prior_release_id"], ["bootstrap_schedule_release.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["current_authorized_context_id"],
            ["authorized_context_version.id"],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("new_source_version_id", name="uq_bootstrap_delta_new_source"),
        sa.UniqueConstraint("project_id", "idempotency_key", name="uq_bootstrap_delta_idem"),
    )
    for column in (
        "organization_id",
        "project_id",
        "prior_source_version_id",
        "new_source_version_id",
    ):
        op.create_index(
            f"ix_bootstrap_revision_delta_{column}", "bootstrap_revision_delta", [column]
        )
    op.execute("""
        CREATE TRIGGER bootstrap_revision_delta_append_only
        BEFORE UPDATE OR DELETE ON bootstrap_revision_delta
        FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER bootstrap_revision_delta_append_only ON bootstrap_revision_delta")
    op.drop_table("bootstrap_revision_delta")
