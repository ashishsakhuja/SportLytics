"""widen_games_phase

Revision ID: 24784645b66c
Revises: fce4cb71412e
Create Date: 2026-03-21 20:34:42.204014

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '24784645b66c'
down_revision: Union[str, None] = 'fce4cb71412e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.alter_column(
        "games",
        "phase",
        existing_type=sa.String(length=10),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade():
    op.alter_column(
        "games",
        "phase",
        existing_type=sa.Text(),
        type_=sa.String(length=10),
        existing_nullable=True,
    )
