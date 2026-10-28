"""Protect authorized context payloads and baseline history; permit only terminal supersession."""

from alembic import op

revision = "0032_context_history_guard"
down_revision = "0031_audit_append_only"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE FUNCTION protect_authorized_context_history() RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'UPDATE' THEN
                IF OLD.semantic_state = 'CURRENT_AUTHORIZED'
                    AND NEW.semantic_state = 'SUPERSEDED'
                    AND OLD.superseded_at IS NULL
                    AND NEW.superseded_at IS NOT NULL
                    AND NEW.superseded_at >= COALESCE(OLD.activated_at, OLD.created_at)
                    AND (to_jsonb(NEW) - ARRAY['semantic_state', 'superseded_at'])
                        = (to_jsonb(OLD) - ARRAY['semantic_state', 'superseded_at'])
                THEN
                    RETURN NEW;
                END IF;
            END IF;
            RAISE EXCEPTION 'authorized_context_version history is immutable';
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER authorized_context_history_rows
        BEFORE UPDATE OR DELETE ON authorized_context_version
        FOR EACH ROW EXECUTE FUNCTION protect_authorized_context_history();
    """)
    op.execute("""
        CREATE TRIGGER authorized_context_history_truncate
        BEFORE TRUNCATE ON authorized_context_version
        FOR EACH STATEMENT EXECUTE FUNCTION protect_authorized_context_history();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER authorized_context_history_truncate ON authorized_context_version")
    op.execute("DROP TRIGGER authorized_context_history_rows ON authorized_context_version")
    op.execute("DROP FUNCTION protect_authorized_context_history()")
