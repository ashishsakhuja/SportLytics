"""add community auto thread fields

Revision ID: b8e0c2d1f712
Revises: a7d2f9cbb001
Create Date: 2026-03-16 15:05:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8e0c2d1f712"
down_revision: Union[str, None] = "f1c4d8eab321"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("community_threads", sa.Column("auto_source_kind", sa.String(length=40), nullable=True))
    op.add_column("community_threads", sa.Column("auto_source_key", sa.String(length=160), nullable=True))
    op.create_index("ix_community_threads_auto_source_kind", "community_threads", ["auto_source_kind"])
    op.create_index("ix_community_threads_auto_source_key", "community_threads", ["auto_source_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_community_threads_auto_source_key", table_name="community_threads")
    op.drop_index("ix_community_threads_auto_source_kind", table_name="community_threads")
    op.drop_column("community_threads", "auto_source_key")
    op.drop_column("community_threads", "auto_source_kind")
