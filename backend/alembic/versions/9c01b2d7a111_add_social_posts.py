"""add_social_posts

Revision ID: 9c01b2d7a111
Revises: <PUT_YOUR_CURRENT_HEAD_REVISION_ID_HERE>
Create Date: 2026-01-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "9c01b2d7a111"
down_revision = "3736475d9465"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "social_posts",
        sa.Column("id", sa.Integer(), primary_key=True),

        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.Column("handle", sa.String(length=80), nullable=False),
        sa.Column("post_id", sa.String(length=200), nullable=False),
        sa.Column("permalink", sa.String(length=600), nullable=False),

        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),

        sa.Column("media_urls", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),

        sa.Column("source_tier", sa.Integer(), nullable=True),
        sa.Column("rank_score", sa.Float(), nullable=True),

        sa.Column("created_db_at", sa.DateTime(), nullable=False),
    )

    op.create_index("ux_social_platform_post_id", "social_posts", ["platform", "post_id"], unique=True)
    op.create_index("ix_social_platform_created_at", "social_posts", ["platform", "created_at"])
    op.create_index("ix_social_posts_platform", "social_posts", ["platform"])
    op.create_index("ix_social_posts_handle", "social_posts", ["handle"])
    op.create_index("ix_social_posts_permalink", "social_posts", ["permalink"], unique=True)
    op.create_index("ix_social_posts_rank_score", "social_posts", ["rank_score"])


def downgrade():
    op.drop_index("ix_social_posts_rank_score", table_name="social_posts")
    op.drop_index("ix_social_posts_permalink", table_name="social_posts")
    op.drop_index("ix_social_posts_handle", table_name="social_posts")
    op.drop_index("ix_social_posts_platform", table_name="social_posts")
    op.drop_index("ix_social_platform_created_at", table_name="social_posts")
    op.drop_index("ux_social_platform_post_id", table_name="social_posts")
    op.drop_table("social_posts")
