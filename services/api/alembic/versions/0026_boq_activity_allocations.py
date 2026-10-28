"""Add explicit BOQ-to-activity allocation lineage."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0026_boq_activity_allocations"
down_revision: str | None = "0025_report_snapshots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "proposed_schedule_activity",
        sa.Column(
            "boq_allocations",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.alter_column("proposed_schedule_activity", "boq_allocations", server_default=None)


def downgrade() -> None:
    op.drop_column("proposed_schedule_activity", "boq_allocations")
