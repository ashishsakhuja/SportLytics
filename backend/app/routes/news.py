from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import ContentItem

router = APIRouter(prefix="/news", tags=["news"])

@router.get("")
def list_news(
    sport: str | None = Query(default=None),
    source: str | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = 50,
    db: Session = Depends(get_db),
):
    query = db.query(ContentItem)

    if sport:
        sports = [s.strip().lower() for s in sport.split(",")]
        query = query.filter(ContentItem.sport.in_(sports))
    if source:
        query = query.filter(ContentItem.source == source)
    if q:
        like = f"%{q}%"
        query = query.filter(ContentItem.title.ilike(like))

    items = query.order_by(ContentItem.published_at.desc()).limit(limit).all()
    return [
        {
            "id": i.id,
            "source": i.source,
            "sport": i.sport,
            "title": i.title,
            "url": i.url,
            "published_at": i.published_at.isoformat(),
            "snippet": i.snippet,
        }
        for i in items
    ]
