"""add teams column

Revision ID: 3736475d9465
Revises: d3a358d60a5f
Create Date: 2026-01-15 20:47:06.570311

"""
from typing import Sequence, Union
from sqlalchemy.dialects import postgresql
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3736475d9465'
down_revision: Union[str, None] = 'd3a358d60a5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("content_items", sa.Column("teams", postgresql.ARRAY(sa.Text()), nullable=True))
    op.create_index(
        "ix_content_items_teams_gin",
        "content_items",
        ["teams"],
        unique=False,
        postgresql_using="gin",
    )


def downgrade() -> None:
    """Downgrade schema."""
    pass
