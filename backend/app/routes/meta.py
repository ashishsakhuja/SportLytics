from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone
from sqlalchemy import text
from ..db import get_db
from ..models import ContentItem, IngestRun
router = APIRouter(prefix="/meta", tags=["meta"])

SPORT_LABELS = {
    "nba": "NBA",
    "nfl": "NFL",
    "cfb": "CFB",
    "mlb": "MLB",
    "nhl": "NHL",
    "f1": "F1",
    "nascar": "NASCAR",
}

@router.get("/sports")
def list_sports_and_sources(db: Session = Depends(get_db)):
    # sport aggregation
    sport_rows = (
        db.query(
            ContentItem.sport,
            func.count(ContentItem.id).label("count"),
            func.max(ContentItem.published_at).label("last_published_at"),
        )
        .group_by(ContentItem.sport)
        .order_by(ContentItem.sport)
        .all()
    )

    sports_out = []
    for sport, count, last_published_at in sport_rows:
        if sport is None:
            continue
        sports_out.append({
            "key": sport,
            "label": SPORT_LABELS.get(sport, sport.upper()),
            "count": int(count),
            "last_published_at": last_published_at.isoformat() if last_published_at else None,
        })

    # source aggregation
    source_rows = (
        db.query(
            ContentItem.source,
            func.count(ContentItem.id).label("count"),
            func.max(ContentItem.published_at).label("last_published_at"),
        )
        .group_by(ContentItem.source)
        .order_by(ContentItem.source)
        .all()
    )

    sources_out = []
    for source, count, last_published_at in source_rows:
        if source is None:
            continue
        sources_out.append({
            "key": source,
            "label": source,
            "count": int(count),
            "last_published_at": last_published_at.isoformat() if last_published_at else None,
        })

    # global last update (nice for footer/status)
    global_last = db.query(func.max(ContentItem.published_at)).scalar()

    return {
        "sports": sports_out,
        "sources": sources_out,
        "global_last_published_at": global_last.isoformat() if global_last else None,
    }

@router.get("/health")
def health(db: Session = Depends(get_db)):
    # Basic DB connectivity check
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    total_items = db.query(func.count(ContentItem.id)).scalar() if db_ok else None
    global_last = db.query(func.max(ContentItem.published_at)).scalar() if db_ok else None

    last_run = (
        db.query(IngestRun)
        .order_by(IngestRun.started_at.desc())
        .first()
    )

    last_run_out = None
    if last_run:
        last_run_out = {
            "id": last_run.id,
            "status": last_run.status,
            "started_at": last_run.started_at.isoformat() if last_run.started_at else None,
            "finished_at": last_run.finished_at.isoformat() if last_run.finished_at else None,
            "inserted_count": last_run.inserted_count,
            "error": last_run.error,
        }

    return {
        "status": "ok" if db_ok else "degraded",
        "db": {"ok": db_ok},
        "content_items": {
            "total": int(total_items) if total_items is not None else None,
            "latest_published_at": global_last.isoformat() if global_last else None,
        },
        "ingestion": {
            "last_run": last_run_out
        },
        "server_time_utc": datetime.now(timezone.utc).isoformat(),
    }

