"""Freeze project health policies, RAG results, and supporting context on control snapshots."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0029_snapshot_health"
down_revision: str | None = "0028_progress_workbook_imports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for column in ("supporting_context", "health"):
        op.add_column(
            "project_control_snapshot",
            sa.Column(
                column,
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )


def downgrade() -> None:
    if op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM project_control_snapshot "
            "WHERE health <> '{}'::jsonb OR supporting_context <> '{}'::jsonb)"
        )
    ):
        raise RuntimeError(
            "Cannot drop immutable health/context history; "
            "retain schema or restore an authorized backup"
        )
    op.drop_column("project_control_snapshot", "health")
    op.drop_column("project_control_snapshot", "supporting_context")
