from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import ContentItem

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import ARRAY
import sqlalchemy as sa


router = APIRouter(prefix="/feed", tags=["feed"])


# ---- DB dependency (kept local so this file works even if you don't have get_db()) ----
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _utc_now_naive() -> datetime:
    # Your DB stores naive UTC datetimes (published_at is naive UTC)
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _time_ago(published_at: Optional[datetime]) -> Optional[str]:
    if not published_at:
        return None
    now = _utc_now_naive()
    delta = now - published_at
    secs = int(delta.total_seconds())
    if secs < 0:
        secs = 0
    mins = secs // 60
    hours = mins // 60
    days = hours // 24
    if days > 0:
        return f"{days}d ago"
    if hours > 0:
        return f"{hours}h ago"
    if mins > 0:
        return f"{mins}m ago"
    return "just now"


def _teams_from_entities(entities: Any) -> List[str]:
    if not entities or not isinstance(entities, dict):
        return []
    teams = entities.get("teams", [])
    if isinstance(teams, list):
        return [str(t) for t in teams]
    return []


def _to_card(item: ContentItem) -> Dict[str, Any]:
    return {
        "id": item.id,
        "title": item.title,
        "source": item.source,
        "sport": item.sport,
        "published_at": item.published_at.isoformat() + "Z" if item.published_at else None,
        "published_ago": _time_ago(item.published_at),
        "url": item.url,
        "snippet": item.snippet,
        "summary": getattr(item, "summary", None),
        "topics": getattr(item, "topics", None) or [],
        "teams": _teams_from_entities(getattr(item, "entities", None)),
        "urgency": getattr(item, "urgency", None),
        "rank_score": getattr(item, "rank_score", None),
        "is_duplicate": getattr(item, "is_duplicate", None),
        "source_tier": getattr(item, "source_tier", None),
        "canonical_id": getattr(item, "canonical_id", None),
        "dedupe_group_id": getattr(item, "dedupe_group_id", None),
    }


@router.get("/top")
def top_feed(
    sport: Optional[str] = Query(default=None, description="Filter by sport (nba/nfl/cfb/mlb/nhl/etc.)"),
    limit: int = Query(default=50, ge=1, le=200),
    include_duplicates: bool = Query(default=False),
    topic: Optional[str] = Query(default=None, description="Filter by a topic tag (injury/trade/betting/etc.)"),
    team: Optional[str] = Query(default=None, description="Filter by team code (LAL, GSW, KC, etc.)"),
    db: Session = Depends(get_db),
):
    q = db.query(ContentItem)

    if sport:
        q = q.filter(ContentItem.sport == sport)

    if not include_duplicates:
        # show only cluster leaders by default
        if hasattr(ContentItem, "is_duplicate"):
            q = q.filter(ContentItem.is_duplicate == False)  # noqa: E712

    if topic:
        # Postgres ARRAY contains element (topics @> ARRAY[topic])
        # SQLAlchemy: topics.contains([topic])
        if hasattr(ContentItem, "topics"):
            q = q.filter(ContentItem.topics.contains([topic]))

    if team:
        team = team.strip().upper()
        q = q.filter(ContentItem.entities.contains({"teams": [team]}))

    # Order by rank_score if present; else fallback to recency
    if hasattr(ContentItem, "rank_score"):
        q = q.order_by(ContentItem.rank_score.desc().nullslast(), ContentItem.published_at.desc())
    else:
        q = q.order_by(ContentItem.published_at.desc())

    items = q.limit(limit).all()
    return {"items": [_to_card(x) for x in items]}


@router.get("/breaking")
def breaking_feed(
    sport: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    min_urgency: float = Query(default=0.9, ge=0.0, le=1.0),
    include_duplicates: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    q = db.query(ContentItem)

    if sport:
        q = q.filter(ContentItem.sport == sport)

    if not include_duplicates and hasattr(ContentItem, "is_duplicate"):
        q = q.filter(ContentItem.is_duplicate == False)  # noqa: E712

    if hasattr(ContentItem, "urgency"):
        q = q.filter(ContentItem.urgency >= min_urgency)

    if hasattr(ContentItem, "rank_score"):
        q = q.order_by(ContentItem.rank_score.desc().nullslast(), ContentItem.published_at.desc())
    else:
        q = q.order_by(ContentItem.published_at.desc())

    items = q.limit(limit).all()
    return {"items": [_to_card(x) for x in items]}
