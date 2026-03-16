"""add community tables

Revision ID: f1c4d8eab321
Revises: e31441cb5fc5
Create Date: 2026-03-16 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1c4d8eab321"
down_revision: Union[str, None] = "7b3c2a1d4f0a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "community_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sport", sa.String(length=30), nullable=True),
        sa.Column("is_private", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_by", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_community_groups_name", "community_groups", ["name"])
    op.create_index("ix_community_groups_sport", "community_groups", ["sport"])
    op.create_index("ix_community_groups_is_private", "community_groups", ["is_private"])
    op.create_index("ix_community_groups_created_by", "community_groups", ["created_by"])
    op.create_index("ix_community_groups_created_at", "community_groups", ["created_at"])

    op.create_table(
        "community_group_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("member_name", sa.String(length=80), nullable=False),
        sa.Column("joined_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("group_id", "member_name", name="ux_community_group_member"),
    )
    op.create_index("ix_community_group_members_group_id", "community_group_members", ["group_id"])
    op.create_index("ix_community_group_members_member_name", "community_group_members", ["member_name"])
    op.create_index("ix_community_group_members_joined_at", "community_group_members", ["joined_at"])

    op.create_table(
        "community_threads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=220), nullable=False),
        sa.Column("created_by", sa.String(length=80), nullable=False),
        sa.Column("is_private", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_community_threads_group_id", "community_threads", ["group_id"])
    op.create_index("ix_community_threads_title", "community_threads", ["title"])
    op.create_index("ix_community_threads_created_by", "community_threads", ["created_by"])
    op.create_index("ix_community_threads_is_private", "community_threads", ["is_private"])
    op.create_index("ix_community_threads_created_at", "community_threads", ["created_at"])
    op.create_index("ix_community_threads_updated_at", "community_threads", ["updated_at"])

    op.create_table(
        "community_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("thread_id", sa.Integer(), nullable=False),
        sa.Column("author", sa.String(length=80), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("shared_plot_title", sa.String(length=200), nullable=True),
        sa.Column("shared_plot_url", sa.String(length=600), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_community_messages_thread_id", "community_messages", ["thread_id"])
    op.create_index("ix_community_messages_author", "community_messages", ["author"])
    op.create_index("ix_community_messages_created_at", "community_messages", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_community_messages_created_at", table_name="community_messages")
    op.drop_index("ix_community_messages_author", table_name="community_messages")
    op.drop_index("ix_community_messages_thread_id", table_name="community_messages")
    op.drop_table("community_messages")

    op.drop_index("ix_community_threads_updated_at", table_name="community_threads")
    op.drop_index("ix_community_threads_created_at", table_name="community_threads")
    op.drop_index("ix_community_threads_is_private", table_name="community_threads")
    op.drop_index("ix_community_threads_created_by", table_name="community_threads")
    op.drop_index("ix_community_threads_title", table_name="community_threads")
    op.drop_index("ix_community_threads_group_id", table_name="community_threads")
    op.drop_table("community_threads")

    op.drop_index("ix_community_group_members_joined_at", table_name="community_group_members")
    op.drop_index("ix_community_group_members_member_name", table_name="community_group_members")
    op.drop_index("ix_community_group_members_group_id", table_name="community_group_members")
    op.drop_table("community_group_members")

    op.drop_index("ix_community_groups_created_at", table_name="community_groups")
    op.drop_index("ix_community_groups_created_by", table_name="community_groups")
    op.drop_index("ix_community_groups_is_private", table_name="community_groups")
    op.drop_index("ix_community_groups_sport", table_name="community_groups")
    op.drop_index("ix_community_groups_name", table_name="community_groups")
    op.drop_table("community_groups")
