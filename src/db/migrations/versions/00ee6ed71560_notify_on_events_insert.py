"""notify on events insert

Revision ID: 00ee6ed71560
Revises: 234fefc4370b
Create Date: 2026-11-26 16:49:17.275129

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '00ee6ed71560'
down_revision: Union[str, Sequence[str], None] = '234fefc4370b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
        CREATE FUNCTION notify_apex_event() RETURNS trigger AS $$
        BEGIN
            PERFORM pg_notify('apex_events', NEW.id::text);
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER events_notify_insert
        AFTER INSERT ON events
        FOR EACH ROW EXECUTE FUNCTION notify_apex_event()
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TRIGGER events_notify_insert ON events")
    op.execute("DROP FUNCTION notify_apex_event()")
