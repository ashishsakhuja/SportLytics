"""add shared plot payload to community messages

Revision ID: c61a4f928d10
Revises: b8e0c2d1f712
Create Date: 2026-03-16 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "c61a4f928d10"
down_revision = "b8e0c2d1f712"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "community_messages",
        sa.Column("shared_plot_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("community_messages", "shared_plot_payload")
