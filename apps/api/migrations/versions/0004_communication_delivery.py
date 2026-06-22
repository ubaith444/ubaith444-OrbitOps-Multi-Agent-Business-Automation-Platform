"""Add communication messages and immutable provider event history."""

from alembic import op

from app.models import CommunicationMessage, MessageEvent

revision = "0004_communication_delivery"
down_revision = "0003_p1_approval_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    CommunicationMessage.__table__.create(bind=bind, checkfirst=True)
    MessageEvent.__table__.create(bind=bind, checkfirst=True)
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE OR REPLACE FUNCTION prevent_message_event_mutation()
            RETURNS trigger AS $$
            BEGIN
              RAISE EXCEPTION 'message_events are append-only';
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            """
            CREATE TRIGGER message_events_immutable
            BEFORE UPDATE OR DELETE ON message_events
            FOR EACH ROW EXECUTE FUNCTION prevent_message_event_mutation();
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS message_events_immutable ON message_events")
        op.execute("DROP FUNCTION IF EXISTS prevent_message_event_mutation")
    MessageEvent.__table__.drop(bind=bind, checkfirst=True)
    CommunicationMessage.__table__.drop(bind=bind, checkfirst=True)
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS messagestatus")
        op.execute("DROP TYPE IF EXISTS messagedirection")
        op.execute("DROP TYPE IF EXISTS communicationchannel")
