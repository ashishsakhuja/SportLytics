from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import (
    CommunityGroup,
    CommunityGroupMember,
    CommunityMessage,
    CommunityThread,
)

router = APIRouter(prefix="/community", tags=["community"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _clean_name(value: str, fallback: str = "Guest") -> str:
    v = (value or "").strip()
    return v[:80] if v else fallback


def _is_member(db: Session, group_id: int, viewer: str) -> bool:
    viewer = _clean_name(viewer, "")
    if not viewer:
        return False
    return db.query(CommunityGroupMember.id).filter(
        CommunityGroupMember.group_id == group_id,
        CommunityGroupMember.member_name == viewer,
    ).first() is not None


def _ensure_access(db: Session, group: CommunityGroup, viewer: str) -> None:
    if group.is_private and not _is_member(db, group.id, viewer):
        raise HTTPException(status_code=403, detail="This private group requires membership.")




def _seed_if_empty(db: Session) -> None:
    if db.query(CommunityGroup.id).first() is not None:
        return

    now = datetime.utcnow()
    seed_groups = [
        {
            "name": "NFL Film Room",
            "description": "Share matchup plots, recent movers, and weekly takes.",
            "sport": "NFL",
            "is_private": False,
            "created_by": "PulseTeam",
            "thread": {
                "title": "Which offense is heating up fastest?",
                "body": "Drop your last-5 vs previous-5 offensive trend plots here.",
                "author": "PulseTeam",
                "shared_plot_title": "NFL Dashboard",
                "shared_plot_url": "/dashboard/nfl",
            },
        },
        {
            "name": "NBA Shot Quality",
            "description": "Discuss team form, playoff risers, and efficiency shifts.",
            "sport": "NBA",
            "is_private": False,
            "created_by": "PulseTeam",
            "thread": {
                "title": "Best under-the-radar playoff riser",
                "body": "Who is trending up without getting enough attention yet?",
                "author": "PulseTeam",
                "shared_plot_title": "NBA Dashboard",
                "shared_plot_url": "/dashboard/nba",
            },
        },
        {
            "name": "Friends Pick Circle",
            "description": "Private room for your own plot shares and pick discussion.",
            "sport": "Mixed",
            "is_private": True,
            "created_by": "Ash",
            "thread": {
                "title": "Sunday locks",
                "body": "Keep private slate notes and shared plots in here.",
                "author": "Ash",
                "shared_plot_title": None,
                "shared_plot_url": None,
            },
        },
    ]
    for item in seed_groups:
        group = CommunityGroup(
            name=item["name"],
            description=item["description"],
            sport=item["sport"],
            is_private=item["is_private"],
            created_by=item["created_by"],
            created_at=now,
        )
        db.add(group)
        db.flush()
        db.add(CommunityGroupMember(group_id=group.id, member_name=item["created_by"]))
        thread = CommunityThread(
            group_id=group.id,
            title=item["thread"]["title"],
            created_by=item["thread"]["author"],
            is_private=item["is_private"],
            created_at=now,
            updated_at=now,
        )
        db.add(thread)
        db.flush()
        db.add(CommunityMessage(
            thread_id=thread.id,
            author=item["thread"]["author"],
            body=item["thread"]["body"],
            shared_plot_title=item["thread"]["shared_plot_title"],
            shared_plot_url=item["thread"]["shared_plot_url"],
            created_at=now,
        ))
    db.commit()

def _group_payload(db: Session, group: CommunityGroup, viewer: str) -> dict:
    member_count = db.query(func.count(CommunityGroupMember.id)).filter(
        CommunityGroupMember.group_id == group.id
    ).scalar() or 0
    thread_count = db.query(func.count(CommunityThread.id)).filter(
        CommunityThread.group_id == group.id
    ).scalar() or 0
    latest_thread = db.query(CommunityThread).filter(
        CommunityThread.group_id == group.id
    ).order_by(CommunityThread.updated_at.desc(), CommunityThread.created_at.desc()).first()
    return {
        "id": group.id,
        "name": group.name,
        "description": group.description,
        "sport": group.sport,
        "is_private": group.is_private,
        "created_by": group.created_by,
        "created_at": group.created_at.isoformat() if group.created_at else None,
        "member_count": int(member_count),
        "thread_count": int(thread_count),
        "is_member": _is_member(db, group.id, viewer),
        "latest_thread_title": latest_thread.title if latest_thread else None,
        "latest_activity_at": (latest_thread.updated_at or latest_thread.created_at).isoformat() if latest_thread else None,
    }


def _thread_payload(db: Session, thread: CommunityThread) -> dict:
    message_count = db.query(func.count(CommunityMessage.id)).filter(
        CommunityMessage.thread_id == thread.id
    ).scalar() or 0
    latest_message = db.query(CommunityMessage).filter(
        CommunityMessage.thread_id == thread.id
    ).order_by(CommunityMessage.created_at.desc()).first()
    return {
        "id": thread.id,
        "group_id": thread.group_id,
        "title": thread.title,
        "created_by": thread.created_by,
        "is_private": thread.is_private,
        "created_at": thread.created_at.isoformat() if thread.created_at else None,
        "updated_at": thread.updated_at.isoformat() if thread.updated_at else None,
        "message_count": int(message_count),
        "latest_message_preview": (latest_message.body[:140] if latest_message else None),
    }


def _message_payload(message: CommunityMessage) -> dict:
    return {
        "id": message.id,
        "thread_id": message.thread_id,
        "author": message.author,
        "body": message.body,
        "shared_plot_title": message.shared_plot_title,
        "shared_plot_url": message.shared_plot_url,
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }


class GroupCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    sport: Optional[str] = Field(default="Mixed", max_length=30)
    is_private: bool = False
    created_by: str = Field(default="Guest", max_length=80)


class JoinGroupRequest(BaseModel):
    viewer: str = Field(..., min_length=1, max_length=80)


class ThreadCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=220)
    body: str = Field(..., min_length=1, max_length=4000)
    author: str = Field(default="Guest", max_length=80)
    is_private: bool = False
    shared_plot_title: Optional[str] = Field(default=None, max_length=200)
    shared_plot_url: Optional[str] = Field(default=None, max_length=600)


class MessageCreate(BaseModel):
    author: str = Field(default="Guest", max_length=80)
    body: str = Field(..., min_length=1, max_length=4000)
    shared_plot_title: Optional[str] = Field(default=None, max_length=200)
    shared_plot_url: Optional[str] = Field(default=None, max_length=600)


@router.get('/groups')
def list_groups(viewer: str = "", db: Session = Depends(get_db)):
    _seed_if_empty(db)
    groups = db.query(CommunityGroup).order_by(
        CommunityGroup.is_private.asc(),
        CommunityGroup.created_at.desc(),
    ).all()
    visible = [g for g in groups if (not g.is_private) or _is_member(db, g.id, viewer)]
    return {"items": [_group_payload(db, g, viewer) for g in visible]}


@router.post('/groups')
def create_group(payload: GroupCreate, db: Session = Depends(get_db)):
    creator = _clean_name(payload.created_by)
    group = CommunityGroup(
        name=payload.name.strip(),
        description=(payload.description or "").strip() or None,
        sport=(payload.sport or "Mixed").strip()[:30],
        is_private=payload.is_private,
        created_by=creator,
    )
    db.add(group)
    db.flush()
    db.add(CommunityGroupMember(group_id=group.id, member_name=creator))
    db.commit()
    db.refresh(group)
    return {"ok": True, "group": _group_payload(db, group, creator)}


@router.post('/groups/{group_id}/join')
def join_group(group_id: int, payload: JoinGroupRequest, db: Session = Depends(get_db)):
    group = db.get(CommunityGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    viewer = _clean_name(payload.viewer)
    exists = db.query(CommunityGroupMember.id).filter(
        CommunityGroupMember.group_id == group_id,
        CommunityGroupMember.member_name == viewer,
    ).first()
    if not exists:
        db.add(CommunityGroupMember(group_id=group_id, member_name=viewer))
        db.commit()
    return {"ok": True, "group": _group_payload(db, group, viewer)}


@router.get('/groups/{group_id}/threads')
def list_threads(group_id: int, viewer: str = "", db: Session = Depends(get_db)):
    group = db.get(CommunityGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    _ensure_access(db, group, viewer)
    threads = db.query(CommunityThread).filter(
        CommunityThread.group_id == group_id
    ).order_by(CommunityThread.updated_at.desc(), CommunityThread.created_at.desc()).all()
    return {
        "group": _group_payload(db, group, viewer),
        "items": [_thread_payload(db, t) for t in threads],
    }


@router.post('/groups/{group_id}/threads')
def create_thread(group_id: int, payload: ThreadCreate, db: Session = Depends(get_db)):
    group = db.get(CommunityGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    author = _clean_name(payload.author)
    if group.is_private and not _is_member(db, group.id, author):
        db.add(CommunityGroupMember(group_id=group.id, member_name=author))
        db.flush()
    now = datetime.utcnow()
    thread = CommunityThread(
        group_id=group.id,
        title=payload.title.strip(),
        created_by=author,
        is_private=group.is_private or payload.is_private,
        created_at=now,
        updated_at=now,
    )
    db.add(thread)
    db.flush()
    db.add(CommunityMessage(
        thread_id=thread.id,
        author=author,
        body=payload.body.strip(),
        shared_plot_title=(payload.shared_plot_title or "").strip() or None,
        shared_plot_url=(payload.shared_plot_url or "").strip() or None,
        created_at=now,
    ))
    db.commit()
    db.refresh(thread)
    return {"ok": True, "thread": _thread_payload(db, thread)}


@router.get('/threads/{thread_id}')
def get_thread(thread_id: int, viewer: str = "", db: Session = Depends(get_db)):
    thread = db.get(CommunityThread, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    group = db.get(CommunityGroup, thread.group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    _ensure_access(db, group, viewer)
    messages = db.query(CommunityMessage).filter(
        CommunityMessage.thread_id == thread_id
    ).order_by(CommunityMessage.created_at.asc()).all()
    return {
        "group": _group_payload(db, group, viewer),
        "thread": _thread_payload(db, thread),
        "messages": [_message_payload(m) for m in messages],
    }


@router.post('/threads/{thread_id}/messages')
def create_message(thread_id: int, payload: MessageCreate, db: Session = Depends(get_db)):
    thread = db.get(CommunityThread, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    group = db.get(CommunityGroup, thread.group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    author = _clean_name(payload.author)
    if group.is_private and not _is_member(db, group.id, author):
        raise HTTPException(status_code=403, detail="Join the private group before posting.")
    now = datetime.utcnow()
    message = CommunityMessage(
        thread_id=thread.id,
        author=author,
        body=payload.body.strip(),
        shared_plot_title=(payload.shared_plot_title or "").strip() or None,
        shared_plot_url=(payload.shared_plot_url or "").strip() or None,
        created_at=now,
    )
    thread.updated_at = now
    db.add(message)
    db.add(thread)
    db.commit()
    db.refresh(message)
    return {"ok": True, "message": _message_payload(message)}
