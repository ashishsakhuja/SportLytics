from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from app.db import SessionLocal
from app.models import SocialPost


router = APIRouter(prefix="/social", tags=["social"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _time_ago(dt: Optional[datetime]) -> Optional[str]:
    if not dt:
        return None
    delta = _utc_now_naive() - dt
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


def _basic_rank(created_at: Optional[datetime]) -> float:
    # embed-only: keep it simple (newer = higher)
    if not created_at:
        return 0.0
    age_hours = (_utc_now_naive() - created_at).total_seconds() / 3600.0
    age_hours = max(0.0, age_hours)
    return float(1.0 / (1.0 + age_hours / 6.0))  # ~0.5 at 6h


def _derive_post_id(platform: str, permalink: str) -> str:
    # lightweight + stable; good enough for embed-only
    # (keeps uniqueness even if platform parsing changes)
    return f"{platform}:{permalink.strip()}"


def _to_card(p: SocialPost) -> Dict[str, Any]:
    return {
        "id": p.id,
        "platform": p.platform,
        "handle": p.handle,
        "post_id": p.post_id,
        "permalink": p.permalink,
        "text": p.text,
        "created_at": p.created_at.isoformat() + "Z" if p.created_at else None,
        "created_ago": _time_ago(p.created_at),
        "media_urls": p.media_urls or [],
        "metrics": p.metrics or {},
        "source_tier": p.source_tier,
        "rank_score": p.rank_score,
    }


@router.get("/top")
def social_top(
    platform: Optional[str] = Query(default=None, description="x or instagram"),
    handle: Optional[str] = Query(default=None, description="filter by account handle"),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(SocialPost)

    if platform:
        q = q.filter(SocialPost.platform == platform)

    if handle:
        q = q.filter(SocialPost.handle == handle.strip().lstrip("@"))

    # best-first: rank_score then recency
    q = q.order_by(SocialPost.rank_score.desc().nullslast(), SocialPost.created_at.desc())

    posts = q.limit(limit).all()
    return {"items": [_to_card(p) for p in posts]}


@router.post("/add")
def social_add(
    platform: str = Body(..., embed=True),     # "x" or "instagram"
    handle: str = Body(..., embed=True),       # "sportscenter"
    permalink: str = Body(..., embed=True),    # full post URL
    text: Optional[str] = Body(default=None, embed=True),
    media_urls: Optional[List[str]] = Body(default=None, embed=True),
    source_tier: int = Body(default=2, embed=True),
    created_at: Optional[datetime] = Body(default=None, embed=True),
    db: Session = Depends(get_db),
):
    platform = (platform or "").strip().lower()
    if platform not in ("x", "instagram"):
        return {"ok": False, "error": "platform_must_be_x_or_instagram"}

    handle = (handle or "").strip().lstrip("@")
    if not handle:
        return {"ok": False, "error": "missing_handle"}

    permalink = (permalink or "").strip()
    if not permalink:
        return {"ok": False, "error": "missing_permalink"}

    # If created_at not provided, use now (fine for embeds)
    created_at = created_at or _utc_now_naive()
    post_id = _derive_post_id(platform, permalink)

    # Dedupe by (platform, post_id) and permalink uniqueness
    exists = (
        db.query(SocialPost.id)
        .filter(SocialPost.platform == platform, SocialPost.post_id == post_id)
        .first()
    )
    if exists:
        return {"ok": True, "inserted": 0}

    rank_score = _basic_rank(created_at)

    sp = SocialPost(
        platform=platform,
        handle=handle,
        post_id=post_id,
        permalink=permalink,
        text=text,
        created_at=created_at,
        media_urls=media_urls or [],
        metrics={},
        source_tier=source_tier,
        rank_score=rank_score,
    )
    db.add(sp)
    db.commit()
    return {"ok": True, "inserted": 1, "id": sp.id}


class SocialBulkItem(BaseModel):
    platform: str = Field(..., description="x or instagram")
    handle: str = Field(..., description="account handle, e.g. SportsCenter")
    permalink: str = Field(..., description="full post url")
    text: Optional[str] = Field(default=None)
    media_urls: Optional[List[str]] = Field(default=None)
    source_tier: int = Field(default=2)
    created_at: Optional[datetime] = Field(default=None)


class SocialBulkRequest(BaseModel):
    items: List[SocialBulkItem]


@router.post("/bulk_add")
def social_bulk_add(
    payload: SocialBulkRequest,
    db: Session = Depends(get_db),
):
    inserted = 0
    skipped = 0
    errors: List[Dict[str, Any]] = []

    for it in payload.items:
        platform = (it.platform or "").strip().lower()
        if platform not in ("x", "instagram"):
            errors.append({"permalink": it.permalink, "error": "platform_must_be_x_or_instagram"})
            skipped += 1
            continue

        handle = (it.handle or "").strip().lstrip("@")
        if not handle:
            errors.append({"permalink": it.permalink, "error": "missing_handle"})
            skipped += 1
            continue

        permalink = (it.permalink or "").strip()
        if not permalink:
            errors.append({"permalink": it.permalink, "error": "missing_permalink"})
            skipped += 1
            continue

        created_at = it.created_at or _utc_now_naive()
        post_id = _derive_post_id(platform, permalink)

        exists = (
            db.query(SocialPost.id)
            .filter(SocialPost.platform == platform, SocialPost.post_id == post_id)
            .first()
        )
        if exists:
            skipped += 1
            continue

        sp = SocialPost(
            platform=platform,
            handle=handle,
            post_id=post_id,
            permalink=permalink,
            text=it.text,
            created_at=created_at,
            media_urls=(it.media_urls or []),
            metrics={},
            source_tier=it.source_tier,
            rank_score=_basic_rank(created_at),
        )
        db.add(sp)
        inserted += 1

    # one commit for the whole batch
    db.commit()

    return {
        "ok": True,
        "inserted": inserted,
        "skipped": skipped,
        "errors": errors,
        "total": len(payload.items),
    }

