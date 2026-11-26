"""add events table

Revision ID: 234fefc4370b
Revises: 2572a0e322ab
Create Date: 2026-11-26 11:18:15.362623

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '234fefc4370b'
down_revision: Union[str, Sequence[str], None] = '2572a0e322ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Rendered by Alembic from the Event model; creates only the events table
    op.create_table('events',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('kind', sa.String(length=50), nullable=False),
    sa.Column('source', sa.String(length=30), nullable=False),
    sa.Column('target', sa.String(length=50), nullable=True),
    sa.Column('project_id', sa.UUID(), nullable=True),
    sa.Column('actor', sa.String(length=50), nullable=True),
    sa.Column('status', sa.String(length=20), server_default='ok', nullable=False),
    sa.Column('latency_ms', sa.Integer(), nullable=True),
    sa.Column('cost_usd', sa.Numeric(precision=10, scale=6), nullable=True),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_events_created_at', 'events', ['created_at'], unique=False)
    op.create_index('idx_events_kind', 'events', ['kind'], unique=False)
    op.create_index('idx_events_project_created', 'events', ['project_id', 'created_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_events_project_created', table_name='events')
    op.drop_index('idx_events_kind', table_name='events')
    op.drop_index('idx_events_created_at', table_name='events')
    op.drop_table('events')
