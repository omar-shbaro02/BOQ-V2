"""Protect audit provenance against SQL updates, deletes, and truncation."""

from alembic import op

revision = "0031_audit_append_only"
down_revision = "0030_presentation_artifacts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE TRIGGER audit_event_append_only BEFORE UPDATE OR DELETE ON audit_event "
        "FOR EACH ROW EXECUTE FUNCTION reject_append_only_change()"
    )
    op.execute(
        "CREATE TRIGGER audit_event_no_truncate BEFORE TRUNCATE ON audit_event "
        "FOR EACH STATEMENT EXECUTE FUNCTION reject_append_only_change()"
    )


def downgrade() -> None:
    # Removing enforcement does not alter or discard historical rows.
    op.execute("DROP TRIGGER audit_event_no_truncate ON audit_event")
    op.execute("DROP TRIGGER audit_event_append_only ON audit_event")
