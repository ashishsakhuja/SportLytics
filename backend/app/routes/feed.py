from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import ContentItem
from sqlalchemy import func
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


def _group_key():
    """
    Stable 'cluster key' even if dedupe_group_id is NULL.
    If dedupe_group_id exists -> group by it
    else -> treat each row as its own cluster using id as string
    """
    return func.coalesce(ContentItem.dedupe_group_id, func.cast(ContentItem.id, sa.String))


from sqlalchemy.orm import aliased

def _cluster_size_subquery(
    sport: Optional[str] = None,
    topic: Optional[str] = None,
    team: Optional[str] = None,
    min_urgency: Optional[float] = None,
):
    Inner = aliased(ContentItem)

    outer_key = func.coalesce(ContentItem.dedupe_group_id, func.cast(ContentItem.id, sa.String))
    inner_key = func.coalesce(Inner.dedupe_group_id, func.cast(Inner.id, sa.String))

    q = sa.select(func.count(Inner.id)).where(inner_key == outer_key)

    if sport:
        q = q.where(Inner.sport == sport)

    if topic:
        q = q.where(Inner.topics.contains([topic]))

    if team:
        q = q.where(Inner.entities.contains({"teams": [team]}))

    if min_urgency is not None:
        q = q.where(Inner.urgency >= min_urgency)

    return q.scalar_subquery()


def _to_card(item: ContentItem, cluster_size: Optional[int] = None, cluster_sources: Optional[List[str]] = None) -> Dict[str, Any]:
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

        # NEW: clustering UX
        "cluster_size": int(cluster_size) if cluster_size is not None else 1,
        "cluster_sources": cluster_sources or [],

    }



@router.get("/top")
def top_feed(
    sport: Optional[str] = Query(default=None, description="Filter by sport (nba/nfl/cfb/mlb/nhl/etc.)"),
    limit: int = Query(default=50, ge=1, le=200),
    include_duplicates: bool = Query(default=False),
    topic: Optional[str] = Query(default=None, description="Filter by a topic tag (injury/trade/betting/etc.)"),
    team: Optional[str] = Query(default=None, description="Filter by team code (LAL, GSW, KC, etc.)"),
    include_cluster_sources: bool = Query(default=False, description="If true, include distinct source list per cluster"),
    db: Session = Depends(get_db),
):
    # --- build base filters once so cluster_size matches the feed filters ---
    base_filters = []

    if sport:
        base_filters.append(ContentItem.sport == sport)

    if topic and hasattr(ContentItem, "topics"):
        base_filters.append(ContentItem.topics.contains([topic]))

    if team:
        team = team.strip().upper()
        base_filters.append(ContentItem.entities.contains({"teams": [team]}))

    q = db.query(ContentItem)

    if base_filters:
        q = q.filter(*base_filters)

    if not include_duplicates and hasattr(ContentItem, "is_duplicate"):
        q = q.filter(ContentItem.is_duplicate == False)  # noqa: E712

    # Use correlated subquery for cluster size under the same filters
    group_key = _group_key()
    cluster_size_sq = _cluster_size_subquery(
        sport=sport,
        topic=topic if topic else None,
        team=team if team else None,
    ).label("cluster_size")
    q = q.add_columns(cluster_size_sq)

    # Order by rank_score if present; else fallback to recency
    if hasattr(ContentItem, "rank_score"):
        q = q.order_by(ContentItem.rank_score.desc().nullslast(), ContentItem.published_at.desc())
    else:
        q = q.order_by(ContentItem.published_at.desc())

    rows = q.limit(limit).all()  # rows = [(ContentItem, cluster_size), ...]

    items_out = []
    for item, cluster_size in rows:
        sources = []
        if include_cluster_sources and getattr(item, "dedupe_group_id", None):
            sources = [
                r[0]
                for r in (
                    db.query(ContentItem.source)
                    .filter(ContentItem.dedupe_group_id == item.dedupe_group_id)
                    .distinct()
                    .all()
                )
            ]

        items_out.append(_to_card(item, cluster_size=cluster_size, cluster_sources=sources))

    return {"items": items_out}


@router.get("/breaking")
def breaking_feed(
    sport: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    min_urgency: float = Query(default=0.9, ge=0.0, le=1.0),
    include_duplicates: bool = Query(default=False),
    include_cluster_sources: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    base_filters = []

    if sport:
        base_filters.append(ContentItem.sport == sport)

    if hasattr(ContentItem, "urgency"):
        base_filters.append(ContentItem.urgency >= min_urgency)

    q = db.query(ContentItem)

    if base_filters:
        q = q.filter(*base_filters)

    if not include_duplicates and hasattr(ContentItem, "is_duplicate"):
        q = q.filter(ContentItem.is_duplicate == False)  # noqa: E712

    group_key = _group_key()
    cluster_size_sq = _cluster_size_subquery(
        sport=sport,
        min_urgency=min_urgency,
    ).label("cluster_size")
    q = q.add_columns(cluster_size_sq)

    if hasattr(ContentItem, "rank_score"):
        q = q.order_by(ContentItem.rank_score.desc().nullslast(), ContentItem.published_at.desc())
    else:
        q = q.order_by(ContentItem.published_at.desc())

    rows = q.limit(limit).all()

    items_out = []
    for item, cluster_size in rows:
        sources = []
        if include_cluster_sources and getattr(item, "dedupe_group_id", None):
            sources = [
                r[0]
                for r in (
                    db.query(ContentItem.source)
                    .filter(ContentItem.dedupe_group_id == item.dedupe_group_id)
                    .distinct()
                    .all()
                )
            ]
        items_out.append(_to_card(item, cluster_size=cluster_size, cluster_sources=sources))

    return {"items": items_out}

@router.get("/cluster/{dedupe_group_id}")
def get_cluster(
    dedupe_group_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(ContentItem).filter(ContentItem.dedupe_group_id == dedupe_group_id)

    # Order duplicates by "best first"
    if hasattr(ContentItem, "rank_score"):
        if hasattr(ContentItem, "source_tier"):
            q = q.order_by(
                ContentItem.rank_score.desc().nullslast(),
                ContentItem.source_tier.desc().nullslast(),
                ContentItem.published_at.desc(),
            )
        else:
            q = q.order_by(
                ContentItem.rank_score.desc().nullslast(),
                ContentItem.published_at.desc(),
            )
    else:
        q = q.order_by(ContentItem.published_at.desc())

    items = q.limit(limit).all()
    return {"items": [_to_card(x) for x in items]}
