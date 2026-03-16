from sqlalchemy import String, DateTime, Text, Index
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from .db import Base
from sqlalchemy import String, DateTime, Integer
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import Boolean, Float
from sqlalchemy.dialects import postgresql


class ContentItem(Base):
    __tablename__ = "content_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(80), index=True)
    sport: Mapped[str] = mapped_column(String(30), index=True)  # "nba","nfl","cfb","f1","nascar"
    team: Mapped[str | None] = mapped_column(String(80), index=True, nullable=True)

    title: Mapped[str] = mapped_column(String(300))
    url: Mapped[str] = mapped_column(String(600), unique=True, index=True)
    published_at: Mapped[datetime] = mapped_column(DateTime, index=True)

    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    canonical_id = sa.Column(sa.Text, nullable=True, index=True)
    dedupe_group_id = sa.Column(sa.Text, nullable=True, index=True)

    topics = sa.Column(ARRAY(sa.Text), nullable=True)
    urgency = sa.Column(sa.Float, nullable=True)
    sentiment = sa.Column(sa.Float, nullable=True)

    teams = sa.Column(postgresql.ARRAY(sa.Text()), nullable=True)
    entities = sa.Column(JSONB, nullable=True)  # {"teams":[...], "players":[...], "leagues":[...]}
    summary = sa.Column(sa.Text, nullable=True)
    key_points = sa.Column(ARRAY(sa.Text), nullable=True)
    confidence = sa.Column(sa.Float, nullable=True)

    source_tier = sa.Column(sa.Integer, nullable=True)
    rank_score = sa.Column(sa.Float, nullable=True, index=True)
    is_duplicate = sa.Column(sa.Boolean, nullable=False, server_default=sa.text("false"))


Index("ix_content_sport_published", ContentItem.sport, ContentItem.published_at)


class IngestRun(Base):
    __tablename__ = "ingest_runs"

    id: Mapped[int] = mapped_column(primary_key=True)

    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="running", index=True)  # running/success/failed
    inserted_count: Mapped[int] = mapped_column(Integer, default=0)

    error: Mapped[str | None] = mapped_column(String(2000), nullable=True)


class SocialPost(Base):
    __tablename__ = "social_posts"

    id: Mapped[int] = mapped_column(primary_key=True)

    platform: Mapped[str] = mapped_column(String(20), index=True)  # "x" | "instagram"
    handle: Mapped[str] = mapped_column(String(80), index=True)  # "sportscenter", "nba", etc.
    post_id: Mapped[str] = mapped_column(String(200), index=True)  # derived id (or permalink)
    permalink: Mapped[str] = mapped_column(String(600), unique=True, index=True)

    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    media_urls = sa.Column(postgresql.ARRAY(sa.Text()), nullable=True)
    metrics = sa.Column(JSONB, nullable=True)  # embed-only: usually empty

    source_tier = sa.Column(sa.Integer, nullable=True)
    rank_score = sa.Column(sa.Float, nullable=True, index=True)

    created_db_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


Index("ux_social_platform_post_id", SocialPost.platform, SocialPost.post_id, unique=True)
Index("ix_social_platform_created_at", SocialPost.platform, SocialPost.created_at)


# -----------------------------
# Sports Data Models (Dashboards)
# -----------------------------

from sqlalchemy import UniqueConstraint


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)

    sport: Mapped[str] = mapped_column(String(30), index=True)  # "nfl", "nba", ...
    team_code: Mapped[str] = mapped_column(String(10), index=True)  # "KC", "BUF", ...
    name: Mapped[str] = mapped_column(String(120))
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)

    meta = sa.Column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        UniqueConstraint("sport", "team_code", name="ux_team_sport_code"),
    )


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(primary_key=True)

    sport: Mapped[str] = mapped_column(String(30), index=True)
    season: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    season_type: Mapped[str | None] = mapped_column(String(10), index=True, nullable=True)  # PRE/REG/POST
    week: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)

    provider: Mapped[str] = mapped_column(String(30), default="nfl_scorestrip", index=True)
    external_game_id: Mapped[str] = mapped_column(String(120), index=True)

    game_date: Mapped[datetime | None] = mapped_column(DateTime, index=True, nullable=True)

    home_team_code: Mapped[str] = mapped_column(String(10), index=True)
    away_team_code: Mapped[str] = mapped_column(String(10), index=True)

    home_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[str | None] = mapped_column(String(30), index=True, nullable=True)  # pre/live/final
    phase: Mapped[str | None] = mapped_column(String(10), nullable=True)  # raw q value from feed

    source_url: Mapped[str | None] = mapped_column(String(600), nullable=True)
    raw = sa.Column(JSONB, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        UniqueConstraint("sport", "provider", "external_game_id", name="ux_game_sport_provider_ext"),
        Index("ix_games_sport_date", "sport", "game_date"),
    )


class StandingsSnapshot(Base):
    __tablename__ = "standings_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)

    sport: Mapped[str] = mapped_column(String(30), index=True)
    season: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    season_type: Mapped[str | None] = mapped_column(String(10), index=True, nullable=True)

    as_of: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    team_code: Mapped[str] = mapped_column(String(10), index=True)
    conference: Mapped[str | None] = mapped_column(String(10), index=True, nullable=True)  # AFC/NFC
    division: Mapped[str | None] = mapped_column(String(20), index=True, nullable=True)  # East/West/etc

    wins: Mapped[int | None] = mapped_column(Integer, nullable=True)
    losses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ties: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)

    source_url: Mapped[str | None] = mapped_column(String(600), nullable=True)
    raw = sa.Column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_standings_sport_season_asof", "sport", "season", "as_of"),
        Index("ix_standings_sport_team_asof", "sport", "team_code", "as_of"),
    )


class TeamGameStats(Base):
    """Per-team, per-game boxscore/advanced stats stored as JSON.

    We keep this sport-agnostic so each sport can write its own stat keys without
    exploding the schema with hundreds of nullable columns.
    """

    __tablename__ = "team_game_stats"

    id: Mapped[int] = mapped_column(primary_key=True)

    sport: Mapped[str] = mapped_column(String(30), index=True)
    game_id: Mapped[int] = mapped_column(Integer, index=True)

    team_code: Mapped[str] = mapped_column(String(10), index=True)
    season: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    season_type: Mapped[str | None] = mapped_column(String(10), index=True, nullable=True)

    # Free-form per-sport stats (standardized keys + raw ESPN keys)
    stats = sa.Column(JSONB, nullable=False)

    source: Mapped[str] = mapped_column(String(60), default="espn_summary", index=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        UniqueConstraint("sport", "game_id", "team_code", name="ux_team_game_stats"),
        Index("ix_team_game_stats_sport_team_season", "sport", "team_code", "season"),
    )


# -----------------------------
# Community Models
# -----------------------------

class CommunityGroup(Base):
    __tablename__ = "community_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sport: Mapped[str | None] = mapped_column(String(30), index=True, nullable=True)
    is_private: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_by: Mapped[str] = mapped_column(String(80), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class CommunityGroupMember(Base):
    __tablename__ = "community_group_members"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(Integer, index=True)
    member_name: Mapped[str] = mapped_column(String(80), index=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        UniqueConstraint("group_id", "member_name", name="ux_community_group_member"),
    )


class CommunityThread(Base):
    __tablename__ = "community_threads"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(Integer, index=True)
    title: Mapped[str] = mapped_column(String(220), index=True)
    created_by: Mapped[str] = mapped_column(String(80), index=True)
    is_private: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    auto_source_kind: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    auto_source_key: Mapped[str | None] = mapped_column(String(160), nullable=True, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class CommunityMessage(Base):
    __tablename__ = "community_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    thread_id: Mapped[int] = mapped_column(Integer, index=True)
    author: Mapped[str] = mapped_column(String(80), index=True)
    body: Mapped[str] = mapped_column(Text)
    shared_plot_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    shared_plot_url: Mapped[str | None] = mapped_column(String(600), nullable=True)
    shared_plot_payload = sa.Column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
