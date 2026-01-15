from sqlalchemy import String, DateTime, Text, Index
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from .db import Base
from sqlalchemy import String, DateTime, Integer

class ContentItem(Base):
    __tablename__ = "content_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(80), index=True)
    sport: Mapped[str] = mapped_column(String(30), index=True)     # "nba","nfl","cfb","f1","nascar"
    team: Mapped[str | None] = mapped_column(String(80), index=True, nullable=True)

    title: Mapped[str] = mapped_column(String(300))
    url: Mapped[str] = mapped_column(String(600), unique=True, index=True)
    published_at: Mapped[datetime] = mapped_column(DateTime, index=True)

    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

Index("ix_content_sport_published", ContentItem.sport, ContentItem.published_at)

class IngestRun(Base):
    __tablename__ = "ingest_runs"

    id: Mapped[int] = mapped_column(primary_key=True)

    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="running", index=True)  # running/success/failed
    inserted_count: Mapped[int] = mapped_column(Integer, default=0)

    error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
