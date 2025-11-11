"""initial schema

Revision ID: 001
Revises:
Create Date: 2025-01-15 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create job_status enum
    op.execute("CREATE TYPE job_status AS ENUM ('queued', 'running', 'success', 'failed')")

    # Create jobs table
    op.create_table(
        'jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('status', postgresql.ENUM('queued', 'running', 'success', 'failed', name='job_status', create_type=False), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('stats_json', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # Create jewels table
    op.create_table(
        'jewels',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('source_url', sa.Text(), nullable=False, unique=True),
        sa.Column('jewel_type', sa.String(length=100), nullable=True),
        sa.Column('metal', sa.String(length=100), nullable=True),
        sa.Column('gemstone', sa.String(length=100), nullable=True),
        sa.Column('gemstone_color', sa.String(length=100), nullable=True),
        sa.Column('metal_color', sa.String(length=100), nullable=True),
        sa.Column('color', sa.String(length=100), nullable=True),
        sa.Column('price_amount', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('price_currency', sa.String(length=10), nullable=True),
        sa.Column('inferred_attributes', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('vibe', sa.String(length=100), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('images', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('raw_metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # Create indexes
    op.create_index('ix_jewels_jewel_type', 'jewels', ['jewel_type'])
    op.create_index('ix_jewels_metal', 'jewels', ['metal'])
    op.create_index('ix_jewels_vibe', 'jewels', ['vibe'])
    op.create_index('idx_jewel_type_metal_vibe', 'jewels', ['jewel_type', 'metal', 'vibe'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_jewel_type_metal_vibe', table_name='jewels')
    op.drop_index('ix_jewels_vibe', table_name='jewels')
    op.drop_index('ix_jewels_metal', table_name='jewels')
    op.drop_index('ix_jewels_jewel_type', table_name='jewels')

    # Drop tables
    op.drop_table('jewels')
    op.drop_table('jobs')

    # Drop enum
    op.execute("DROP TYPE job_status")
