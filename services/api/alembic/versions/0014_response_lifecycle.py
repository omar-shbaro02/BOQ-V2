"""Add governed response proposal, authorization, execution, and outcome history."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014_response_lifecycle"
down_revision: str | None = "0013_human_decisions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())

    def common() -> list[sa.Column]:
        return [
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
                "case_id",
                postgresql.UUID(),
                sa.ForeignKey("decision_case.id", ondelete="RESTRICT"),
                nullable=False,
            ),
        ]

    op.create_table(
        "response_proposal",
        *common(),
        sa.Column(
            "human_decision_id",
            postgresql.UUID(),
            sa.ForeignKey("human_decision.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("proposal_number", sa.Integer(), nullable=False),
        sa.Column("response_type", sa.String(80), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("actions", jsonb, nullable=False),
        sa.Column("assumptions", jsonb, nullable=False),
        sa.Column("simulated_effects", jsonb, nullable=False),
        sa.Column("requested_amount", sa.Numeric(20, 4)),
        sa.Column("currency", sa.String(3)),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("proposed_by", sa.String(200), nullable=False),
        sa.Column(
            "proposed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("case_id", "proposal_number", name="uq_response_proposal_number"),
        sa.UniqueConstraint("case_id", "idempotency_key", name="uq_response_proposal_idempotency"),
    )
    op.create_table(
        "response_authorization",
        *common(),
        sa.Column(
            "proposal_id",
            postgresql.UUID(),
            sa.ForeignKey("response_proposal.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "human_decision_id",
            postgresql.UUID(),
            sa.ForeignKey("human_decision.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "authority_grant_id",
            postgresql.UUID(),
            sa.ForeignKey("authority_grant.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("authorization_reference", sa.String(200), nullable=False, unique=True),
        sa.Column("authority_scope", jsonb, nullable=False),
        sa.Column("authorized_by", sa.String(200), nullable=False),
        sa.Column(
            "authorized_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_table(
        "response_execution_observation",
        *common(),
        sa.Column(
            "proposal_id",
            postgresql.UUID(),
            sa.ForeignKey("response_proposal.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "authorization_id",
            postgresql.UUID(),
            sa.ForeignKey("response_authorization.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("details", jsonb, nullable=False),
        sa.Column("evidence_item_ids", jsonb, nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("recorded_by", sa.String(200), nullable=False),
        sa.Column(
            "recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "proposal_id", "sequence_number", name="uq_response_execution_sequence"
        ),
        sa.UniqueConstraint(
            "proposal_id", "idempotency_key", name="uq_response_execution_idempotency"
        ),
    )
    op.create_table(
        "response_outcome",
        *common(),
        sa.Column(
            "proposal_id",
            postgresql.UUID(),
            sa.ForeignKey("response_proposal.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "authorization_id",
            postgresql.UUID(),
            sa.ForeignKey("response_authorization.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("classification", sa.String(30), nullable=False),
        sa.Column("evidence_item_ids", jsonb, nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("assessed_by", sa.String(200), nullable=False),
        sa.Column(
            "assessed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "proposal_id", "idempotency_key", name="uq_response_outcome_idempotency"
        ),
    )
    for table in (
        "response_proposal",
        "response_authorization",
        "response_execution_observation",
        "response_outcome",
    ):
        for column in ("organization_id", "project_id", "case_id"):
            op.create_index(f"ix_{table}_{column}", table, [column])
        op.execute(f"""
            CREATE TRIGGER {table}_append_only
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
        """)


def downgrade() -> None:
    for table in (
        "response_outcome",
        "response_execution_observation",
        "response_authorization",
        "response_proposal",
    ):
        op.execute(f"DROP TRIGGER {table}_append_only ON {table}")
        op.drop_table(table)
