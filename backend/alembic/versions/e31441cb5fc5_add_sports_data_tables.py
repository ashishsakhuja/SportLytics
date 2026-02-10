"""add sports data tables

Revision ID: e31441cb5fc5
Revises: 9c01b2d7a111
Create Date: 2026-02-10 17:01:55.124501

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "e31441cb5fc5"
down_revision: Union[str, None] = "9c01b2d7a111"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -------------------------
    # teams
    # -------------------------
    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sport", sa.String(length=30), nullable=False),
        sa.Column("team_code", sa.String(length=10), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("sport", "team_code", name="ux_team_sport_code"),
    )
    op.create_index("ix_teams_sport", "teams", ["sport"])
    op.create_index("ix_teams_team_code", "teams", ["team_code"])
    op.create_index("ix_teams_created_at", "teams", ["created_at"])

    # -------------------------
    # games
    # -------------------------
    op.create_table(
        "games",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sport", sa.String(length=30), nullable=False),
        sa.Column("season", sa.Integer(), nullable=True),
        sa.Column("season_type", sa.String(length=10), nullable=True),
        sa.Column("week", sa.Integer(), nullable=True),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("external_game_id", sa.String(length=120), nullable=False),
        sa.Column("game_date", sa.DateTime(), nullable=True),
        sa.Column("home_team_code", sa.String(length=10), nullable=False),
        sa.Column("away_team_code", sa.String(length=10), nullable=False),
        sa.Column("home_score", sa.Integer(), nullable=True),
        sa.Column("away_score", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=True),
        sa.Column("phase", sa.String(length=10), nullable=True),
        sa.Column("source_url", sa.String(length=600), nullable=True),
        sa.Column("raw", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "sport",
            "provider",
            "external_game_id",
            name="ux_game_sport_provider_ext",
        ),
    )

    op.create_index("ix_games_sport", "games", ["sport"])
    op.create_index("ix_games_season", "games", ["season"])
    op.create_index("ix_games_season_type", "games", ["season_type"])
    op.create_index("ix_games_week", "games", ["week"])
    op.create_index("ix_games_provider", "games", ["provider"])
    op.create_index("ix_games_external_game_id", "games", ["external_game_id"])
    op.create_index("ix_games_game_date", "games", ["game_date"])
    op.create_index("ix_games_home_team_code", "games", ["home_team_code"])
    op.create_index("ix_games_away_team_code", "games", ["away_team_code"])
    op.create_index("ix_games_status", "games", ["status"])
    op.create_index("ix_games_updated_at", "games", ["updated_at"])
    op.create_index("ix_games_sport_date", "games", ["sport", "game_date"])

    # -------------------------
    # standings_snapshots
    # -------------------------
    op.create_table(
        "standings_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sport", sa.String(length=30), nullable=False),
        sa.Column("season", sa.Integer(), nullable=True),
        sa.Column("season_type", sa.String(length=10), nullable=True),
        sa.Column("as_of", sa.DateTime(), nullable=False),
        sa.Column("team_code", sa.String(length=10), nullable=False),
        sa.Column("conference", sa.String(length=10), nullable=True),
        sa.Column("division", sa.String(length=20), nullable=True),
        sa.Column("wins", sa.Integer(), nullable=True),
        sa.Column("losses", sa.Integer(), nullable=True),
        sa.Column("ties", sa.Integer(), nullable=True),
        sa.Column("pct", sa.Float(), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("source_url", sa.String(length=600), nullable=True),
        sa.Column("raw", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    op.create_index("ix_standings_snapshots_sport", "standings_snapshots", ["sport"])
    op.create_index("ix_standings_snapshots_season", "standings_snapshots", ["season"])
    op.create_index("ix_standings_snapshots_season_type", "standings_snapshots", ["season_type"])
    op.create_index("ix_standings_snapshots_as_of", "standings_snapshots", ["as_of"])
    op.create_index("ix_standings_snapshots_team_code", "standings_snapshots", ["team_code"])
    op.create_index("ix_standings_snapshots_conference", "standings_snapshots", ["conference"])
    op.create_index("ix_standings_snapshots_division", "standings_snapshots", ["division"])

    op.create_index(
        "ix_standings_sport_season_asof",
        "standings_snapshots",
        ["sport", "season", "as_of"],
    )
    op.create_index(
        "ix_standings_sport_team_asof",
        "standings_snapshots",
        ["sport", "team_code", "as_of"],
    )


def downgrade() -> None:
    # standings_snapshots
    op.drop_index("ix_standings_sport_team_asof", table_name="standings_snapshots")
    op.drop_index("ix_standings_sport_season_asof", table_name="standings_snapshots")
    op.drop_index("ix_standings_snapshots_division", table_name="standings_snapshots")
    op.drop_index("ix_standings_snapshots_conference", table_name="standings_snapshots")
    op.drop_index("ix_standings_snapshots_team_code", table_name="standings_snapshots")
    op.drop_index("ix_standings_snapshots_as_of", table_name="standings_snapshots")
    op.drop_index("ix_standings_snapshots_season_type", table_name="standings_snapshots")
    op.drop_index("ix_standings_snapshots_season", table_name="standings_snapshots")
    op.drop_index("ix_standings_snapshots_sport", table_name="standings_snapshots")
    op.drop_table("standings_snapshots")

    # games
    op.drop_index("ix_games_sport_date", table_name="games")
    op.drop_index("ix_games_updated_at", table_name="games")
    op.drop_index("ix_games_status", table_name="games")
    op.drop_index("ix_games_away_team_code", table_name="games")
    op.drop_index("ix_games_home_team_code", table_name="games")
    op.drop_index("ix_games_game_date", table_name="games")
    op.drop_index("ix_games_external_game_id", table_name="games")
    op.drop_index("ix_games_provider", table_name="games")
    op.drop_index("ix_games_week", table_name="games")
    op.drop_index("ix_games_season_type", table_name="games")
    op.drop_index("ix_games_season", table_name="games")
    op.drop_index("ix_games_sport", table_name="games")
    op.drop_table("games")

    # teams
    op.drop_index("ix_teams_created_at", table_name="teams")
    op.drop_index("ix_teams_team_code", table_name="teams")
    op.drop_index("ix_teams_sport", table_name="teams")
    op.drop_table("teams")
