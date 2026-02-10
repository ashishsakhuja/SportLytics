"""add sports data tables

Revision ID: e31441cb5fc5
Revises: 9c01b2d7a111
Create Date: 2026-02-10 17:01:55.124501

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e31441cb5fc5'
down_revision: Union[str, None] = '9c01b2d7a111'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
