"""add enrichment fields to news_items

Revision ID: d3a358d60a5f
Revises: 462fcc3bda2f
Create Date: 2026-01-15 13:40:30.505692

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "d3a358d60a5f"
down_revision: Union[str, None] = "462fcc3bda2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # --- Columns (safe to re-run) ---
    # Using raw SQL so Postgres can do IF NOT EXISTS.
    op.execute('ALTER TABLE content_items ADD COLUMN IF NOT EXISTS canonical_id TEXT')
    op.execute('ALTER TABLE content_items ADD COLUMN IF NOT EXISTS dedupe_group_id TEXT')
    op.execute('ALTER TABLE content_items ADD COLUMN IF NOT EXISTS topics TEXT[]')
    op.execute('ALTER TABLE content_items ADD COLUMN IF NOT EXISTS urgency DOUBLE PRECISION')
    op.execute('ALTER TABLE content_items ADD COLUMN IF NOT EXISTS sentiment DOUBLE PRECISION')
    op.execute('ALTER TABLE content_items ADD COLUMN IF NOT EXISTS entities JSONB')
    op.execute('ALTER TABLE content_items ADD COLUMN IF NOT EXISTS summary TEXT')
    op.execute('ALTER TABLE content_items ADD COLUMN IF NOT EXISTS key_points TEXT[]')
    op.execute('ALTER TABLE content_items ADD COLUMN IF NOT EXISTS confidence DOUBLE PRECISION')

    op.execute('ALTER TABLE content_items ADD COLUMN IF NOT EXISTS source_tier INTEGER')
    op.execute('ALTER TABLE content_items ADD COLUMN IF NOT EXISTS rank_score DOUBLE PRECISION')

    # Boolean default false; keep it safe for re-runs
    op.execute('ALTER TABLE content_items ADD COLUMN IF NOT EXISTS is_duplicate BOOLEAN DEFAULT FALSE')

    # --- Indexes (safe to re-run) ---
    op.execute("CREATE INDEX IF NOT EXISTS ix_content_items_published_at ON content_items (published_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_content_items_sport_published_at ON content_items (sport, published_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_content_items_canonical_id ON content_items (canonical_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_content_items_dedupe_group_id ON content_items (dedupe_group_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_content_items_rank_score ON content_items (rank_score)")

    op.execute("CREATE INDEX IF NOT EXISTS ix_content_items_entities_gin ON content_items USING gin (entities)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_content_items_topics_gin ON content_items USING gin (topics)")


def downgrade():
    # --- Drop indexes (safe) ---
    op.execute("DROP INDEX IF EXISTS ix_content_items_topics_gin")
    op.execute("DROP INDEX IF EXISTS ix_content_items_entities_gin")
    op.execute("DROP INDEX IF EXISTS ix_content_items_rank_score")
    op.execute("DROP INDEX IF EXISTS ix_content_items_dedupe_group_id")
    op.execute("DROP INDEX IF EXISTS ix_content_items_canonical_id")
    op.execute("DROP INDEX IF EXISTS ix_content_items_sport_published_at")
    op.execute("DROP INDEX IF EXISTS ix_content_items_published_at")

    # --- Drop columns (safe) ---
    op.execute("ALTER TABLE content_items DROP COLUMN IF EXISTS is_duplicate")
    op.execute("ALTER TABLE content_items DROP COLUMN IF EXISTS rank_score")
    op.execute("ALTER TABLE content_items DROP COLUMN IF EXISTS source_tier")
    op.execute("ALTER TABLE content_items DROP COLUMN IF EXISTS confidence")
    op.execute("ALTER TABLE content_items DROP COLUMN IF EXISTS key_points")
    op.execute("ALTER TABLE content_items DROP COLUMN IF EXISTS summary")
    op.execute("ALTER TABLE content_items DROP COLUMN IF EXISTS entities")
    op.execute("ALTER TABLE content_items DROP COLUMN IF EXISTS sentiment")
    op.execute("ALTER TABLE content_items DROP COLUMN IF EXISTS urgency")
    op.execute("ALTER TABLE content_items DROP COLUMN IF EXISTS topics")
    op.execute("ALTER TABLE content_items DROP COLUMN IF EXISTS dedupe_group_id")
    op.execute("ALTER TABLE content_items DROP COLUMN IF EXISTS canonical_id")
