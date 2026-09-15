"""Add authority-validated immutable human decisions."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013_human_decisions"
down_revision: str | None = "0012_contradiction_resolutions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.add_column("decision_case", sa.Column("last_human_decision_id", postgresql.UUID()))
    op.create_table(
        "human_decision",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(), nullable=False),
        sa.Column("project_id", postgresql.UUID(), nullable=False),
        sa.Column("case_id", postgresql.UUID(), nullable=False),
        sa.Column("orchestration_run_id", postgresql.UUID(), nullable=False),
        sa.Column("authority_grant_id", postgresql.UUID(), nullable=False),
        sa.Column("decision_number", sa.Integer(), nullable=False),
        sa.Column("disposition", sa.String(20), nullable=False),
        sa.Column("recommendation_agreement", sa.String(30), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("authority_outcome", sa.String(30), nullable=False),
        sa.Column("authority_scope", jsonb, nullable=False),
        sa.Column("decision_amount", sa.Numeric(20, 4)),
        sa.Column("currency", sa.String(3)),
        sa.Column("limitations", jsonb, nullable=False),
        sa.Column("response_authorization_reference", sa.String(200)),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("decided_by", sa.String(200), nullable=False),
        sa.Column(
            "decided_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["case_id"], ["decision_case.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["orchestration_run_id"], ["orchestration_run.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["authority_grant_id"], ["authority_grant.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("case_id", "decision_number", name="uq_human_decision_number"),
        sa.UniqueConstraint("case_id", "idempotency_key", name="uq_human_decision_idempotency"),
        sa.CheckConstraint("decision_number > 0", name="ck_human_decision_number"),
        sa.CheckConstraint(
            "request_hash ~ '^[0-9a-f]{64}$'", name="ck_human_decision_request_hash"
        ),
    )
    for column in (
        "organization_id",
        "project_id",
        "case_id",
        "orchestration_run_id",
        "authority_grant_id",
    ):
        op.create_index(f"ix_human_decision_{column}", "human_decision", [column])
    op.create_foreign_key(
        "fk_decision_case_last_human_decision",
        "decision_case",
        "human_decision",
        ["last_human_decision_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.execute("""
        CREATE TRIGGER human_decision_append_only
          BEFORE UPDATE OR DELETE ON human_decision
          FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER human_decision_append_only ON human_decision")
    op.drop_constraint("fk_decision_case_last_human_decision", "decision_case", type_="foreignkey")
    op.drop_table("human_decision")
    op.drop_column("decision_case", "last_human_decision_id")
