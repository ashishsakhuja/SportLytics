"""add team_game_stats

Revision ID: 7b3c2a1d4f0a
Revises: e31441cb5fc5
Create Date: 2026-03-03

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "7b3c2a1d4f0a"
down_revision: Union[str, None] = "e31441cb5fc5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "team_game_stats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sport", sa.String(length=30), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("team_code", sa.String(length=10), nullable=False),
        sa.Column("season", sa.Integer(), nullable=True),
        sa.Column("season_type", sa.String(length=10), nullable=True),
        sa.Column("stats", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source", sa.String(length=60), nullable=False, server_default=sa.text("'espn_summary'")),
        sa.Column("ingested_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("sport", "game_id", "team_code", name="ux_team_game_stats"),
    )

    op.create_index("ix_team_game_stats_sport", "team_game_stats", ["sport"])
    op.create_index("ix_team_game_stats_game_id", "team_game_stats", ["game_id"])
    op.create_index("ix_team_game_stats_team_code", "team_game_stats", ["team_code"])
    op.create_index("ix_team_game_stats_season", "team_game_stats", ["season"])
    op.create_index("ix_team_game_stats_season_type", "team_game_stats", ["season_type"])
    op.create_index("ix_team_game_stats_source", "team_game_stats", ["source"])
    op.create_index("ix_team_game_stats_ingested_at", "team_game_stats", ["ingested_at"])
    op.create_index(
        "ix_team_game_stats_sport_team_season",
        "team_game_stats",
        ["sport", "team_code", "season"],
    )


def downgrade() -> None:
    op.drop_index("ix_team_game_stats_sport_team_season", table_name="team_game_stats")
    op.drop_index("ix_team_game_stats_ingested_at", table_name="team_game_stats")
    op.drop_index("ix_team_game_stats_source", table_name="team_game_stats")
    op.drop_index("ix_team_game_stats_season_type", table_name="team_game_stats")
    op.drop_index("ix_team_game_stats_season", table_name="team_game_stats")
    op.drop_index("ix_team_game_stats_team_code", table_name="team_game_stats")
    op.drop_index("ix_team_game_stats_game_id", table_name="team_game_stats")
    op.drop_index("ix_team_game_stats_sport", table_name="team_game_stats")
    op.drop_table("team_game_stats")