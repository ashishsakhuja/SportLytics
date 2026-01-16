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
