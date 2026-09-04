"""Create Phase 1 project and authorized-context tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_control_context"
down_revision: str | None = "0001_bootstrap"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def uuid_column(name: str, *, nullable: bool = False) -> sa.Column:
    return sa.Column(name, postgresql.UUID(as_uuid=True), nullable=nullable)


def created_at_column() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "organization",
        uuid_column("id"),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        created_at_column(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "project",
        uuid_column("id"),
        uuid_column("organization_id"),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("timezone", sa.String(80), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("delivery_model", sa.String(80), nullable=False),
        sa.Column("reporting_cadence", sa.String(40), nullable=False),
        sa.Column("calendar_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        created_at_column(),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_project_currency"),
        sa.CheckConstraint("status IN ('DRAFT', 'ACTIVE', 'ARCHIVED')", name="ck_project_status"),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "code", name="uq_project_org_code"),
    )
    op.create_index("ix_project_organization_id", "project", ["organization_id"])

    op.create_table(
        "membership",
        uuid_column("id"),
        uuid_column("organization_id"),
        uuid_column("project_id", nullable=True),
        sa.Column("actor_id", sa.String(200), nullable=False),
        sa.Column("role", sa.String(60), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        created_at_column(),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_membership_actor_id", "membership", ["actor_id"])
    op.create_index("ix_membership_organization_id", "membership", ["organization_id"])
    op.create_index("ix_membership_project_id", "membership", ["project_id"])
    op.create_index(
        "uq_membership_org_scope",
        "membership",
        ["organization_id", "actor_id", "role"],
        unique=True,
        postgresql_where=sa.text("project_id IS NULL"),
    )
    op.create_index(
        "uq_membership_project_scope",
        "membership",
        ["organization_id", "project_id", "actor_id", "role"],
        unique=True,
        postgresql_where=sa.text("project_id IS NOT NULL"),
    )

    op.create_table(
        "controlled_object",
        uuid_column("id"),
        uuid_column("organization_id"),
        uuid_column("project_id"),
        sa.Column("object_type", sa.String(40), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(240), nullable=False),
        sa.Column("owner_actor_id", sa.String(200), nullable=True),
        sa.Column("attributes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        created_at_column(),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "code", name="uq_controlled_object_project_code"),
    )
    op.create_index("ix_controlled_object_project_id", "controlled_object", ["project_id"])
    op.create_index(
        "ix_controlled_object_organization_id", "controlled_object", ["organization_id"]
    )

    op.create_table(
        "controlled_object_relation",
        uuid_column("id"),
        uuid_column("organization_id"),
        uuid_column("project_id"),
        uuid_column("source_id"),
        uuid_column("target_id"),
        sa.Column("relation_type", sa.String(40), nullable=False),
        created_at_column(),
        sa.CheckConstraint("source_id <> target_id", name="ck_relation_not_self"),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["controlled_object.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_id"], ["controlled_object.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_id", "target_id", "relation_type", name="uq_controlled_object_relation"
        ),
    )
    op.create_index("ix_relation_project_id", "controlled_object_relation", ["project_id"])
    op.create_index("ix_relation_source_id", "controlled_object_relation", ["source_id"])
    op.create_index("ix_relation_target_id", "controlled_object_relation", ["target_id"])

    op.create_table(
        "authority_grant",
        uuid_column("id"),
        uuid_column("organization_id"),
        uuid_column("project_id"),
        sa.Column("actor_id", sa.String(200), nullable=False),
        sa.Column("authority_type", sa.String(80), nullable=False),
        uuid_column("controlled_object_id", nullable=True),
        sa.Column("max_amount", sa.Numeric(20, 4), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("escalation_level", sa.Integer(), nullable=False),
        sa.Column("escalates_to_actor_id", sa.String(200), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "currency IS NULL OR currency ~ '^[A-Z]{3}$'", name="ck_authority_currency"
        ),
        sa.CheckConstraint(
            "valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from",
            name="ck_authority_valid_range",
        ),
        sa.CheckConstraint("escalation_level >= 0", name="ck_authority_escalation_level"),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["controlled_object_id"], ["controlled_object.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_authority_actor_id", "authority_grant", ["actor_id"])
    op.create_index("ix_authority_project_id", "authority_grant", ["project_id"])

    op.create_table(
        "authorized_context_version",
        uuid_column("id"),
        uuid_column("organization_id"),
        uuid_column("project_id"),
        sa.Column("context_type", sa.String(20), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("semantic_state", sa.String(30), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        created_at_column(),
        uuid_column("source_version_id", nullable=True),
        sa.Column("approval_reference", sa.Text(), nullable=True),
        sa.Column("activation_reason", sa.Text(), nullable=True),
        sa.Column("activated_by", sa.String(200), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("context_type IN ('SCHEDULE', 'BUDGET', 'BOQ')", name="ck_context_type"),
        sa.CheckConstraint(
            "semantic_state IN ('BASELINE', 'PROPOSED', 'CURRENT_AUTHORIZED', 'SUPERSEDED')",
            name="ck_context_semantic_state",
        ),
        sa.CheckConstraint("version_number > 0", name="ck_context_version_positive"),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["source_version_id"], ["authorized_context_version.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id", "context_type", "version_number", name="uq_context_project_type_version"
        ),
    )
    op.create_index(
        "ix_context_project_type", "authorized_context_version", ["project_id", "context_type"]
    )
    op.create_index(
        "uq_context_current_authorized",
        "authorized_context_version",
        ["project_id", "context_type"],
        unique=True,
        postgresql_where=sa.text("semantic_state = 'CURRENT_AUTHORIZED'"),
    )
    op.add_column("audit_event", uuid_column("organization_id", nullable=True))
    op.add_column("audit_event", uuid_column("project_id", nullable=True))
    op.create_foreign_key(
        "fk_audit_organization",
        "audit_event",
        "organization",
        ["organization_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_audit_project",
        "audit_event",
        "project",
        ["project_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_audit_organization_id", "audit_event", ["organization_id"])
    op.create_index("ix_audit_project_id", "audit_event", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_project_id", table_name="audit_event")
    op.drop_index("ix_audit_organization_id", table_name="audit_event")
    op.drop_constraint("fk_audit_project", "audit_event", type_="foreignkey")
    op.drop_constraint("fk_audit_organization", "audit_event", type_="foreignkey")
    op.drop_column("audit_event", "project_id")
    op.drop_column("audit_event", "organization_id")
    op.drop_index("uq_context_current_authorized", table_name="authorized_context_version")
    op.drop_index("ix_context_project_type", table_name="authorized_context_version")
    op.drop_table("authorized_context_version")
    op.drop_index("ix_authority_project_id", table_name="authority_grant")
    op.drop_index("ix_authority_actor_id", table_name="authority_grant")
    op.drop_table("authority_grant")
    op.drop_index("ix_relation_target_id", table_name="controlled_object_relation")
    op.drop_index("ix_relation_source_id", table_name="controlled_object_relation")
    op.drop_index("ix_relation_project_id", table_name="controlled_object_relation")
    op.drop_table("controlled_object_relation")
    op.drop_index("ix_controlled_object_organization_id", table_name="controlled_object")
    op.drop_index("ix_controlled_object_project_id", table_name="controlled_object")
    op.drop_table("controlled_object")
    op.drop_index("uq_membership_project_scope", table_name="membership")
    op.drop_index("uq_membership_org_scope", table_name="membership")
    op.drop_index("ix_membership_project_id", table_name="membership")
    op.drop_index("ix_membership_organization_id", table_name="membership")
    op.drop_index("ix_membership_actor_id", table_name="membership")
    op.drop_table("membership")
    op.drop_index("ix_project_organization_id", table_name="project")
    op.drop_table("project")
    op.drop_table("organization")
