"""create signals table

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'signals',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('direction', sa.String(5), nullable=False),
        sa.Column('price', sa.Numeric(20, 8), nullable=False),
        sa.Column('change_15m', sa.Numeric(8, 4), nullable=False),
        sa.Column('rsi_1h', sa.Numeric(6, 2), nullable=False),
        sa.Column('rsi_15m', sa.Numeric(6, 2), nullable=False),
        sa.Column('chart_url', sa.Text(), nullable=True),
        sa.Column('telegram_sent', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('telegram_msg_id', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('idx_signals_symbol', 'signals', ['symbol'])
    op.create_index('idx_signals_created_at', 'signals', ['created_at'])
    op.create_index('idx_signals_direction', 'signals', ['direction'])


def downgrade() -> None:
    op.drop_index('idx_signals_direction', 'signals')
    op.drop_index('idx_signals_created_at', 'signals')
    op.drop_index('idx_signals_symbol', 'signals')
    op.drop_table('signals')