from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Cookie, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import AuthSession, UserAccount
from app.settings import settings

SESSION_DAYS = int(os.getenv('SPORTLYTICS_SESSION_DAYS', '30'))
PBKDF2_ROUNDS = int(os.getenv('SPORTLYTICS_PBKDF2_ROUNDS', '480000'))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def normalize_email(email: str) -> str:
    return (email or '').strip().lower()


def derive_display_name(email: str) -> str:
    local = normalize_email(email).split('@', 1)[0]
    cleaned = ' '.join(
        part for part in local.replace('.', ' ').replace('_', ' ').replace('-', ' ').split() if part
    )
    if not cleaned:
        return 'SportLytics User'
    return cleaned.title()[:80]


def hash_password(password: str) -> str:
    if len(password or '') < 8:
        raise HTTPException(status_code=400, detail='Password must be at least 8 characters.')
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, PBKDF2_ROUNDS)
    return (
        f"pbkdf2_sha256${PBKDF2_ROUNDS}${base64.b64encode(salt).decode()}"
        f"${base64.b64encode(digest).decode()}"
    )


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        scheme, rounds, salt_b64, digest_b64 = stored_hash.split('$', 3)
        if scheme != 'pbkdf2_sha256':
            return False
        salt = base64.b64decode(salt_b64.encode())
        expected = base64.b64decode(digest_b64.encode())
        actual = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, int(rounds))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def create_session(db: Session, user: UserAccount) -> str:
    token = secrets.token_urlsafe(48)
    now = datetime.utcnow()
    session = AuthSession(
        user_id=user.id,
        token=token,
        created_at=now,
        expires_at=now + timedelta(days=SESSION_DAYS),
        last_seen_at=now,
    )
    db.add(session)
    db.flush()
    return token


def _extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        return None
    return parts[1].strip() or None


def _resolve_session_token(authorization: Optional[str], session_cookie: Optional[str]) -> Optional[str]:
    return _extract_bearer_token(authorization) or (session_cookie.strip() if session_cookie else None)


def get_current_user_optional(
    authorization: Optional[str] = Header(default=None),
    session_cookie: Optional[str] = Cookie(default=None, alias=settings.SESSION_COOKIE_NAME),
    db: Session = Depends(get_db),
) -> Optional[UserAccount]:
    token = _resolve_session_token(authorization, session_cookie)
    if not token:
        return None
    now = datetime.utcnow()
    session = (
        db.query(AuthSession)
        .filter(
            AuthSession.token == token,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now,
        )
        .first()
    )
    if not session:
        return None
    user = db.get(UserAccount, session.user_id)
    if not user or not user.is_active:
        return None
    session.last_seen_at = now
    db.add(session)
    db.flush()
    return user


def get_current_user_required(user: Optional[UserAccount] = Depends(get_current_user_optional)) -> UserAccount:
    if not user:
        raise HTTPException(status_code=401, detail='Sign in required')
    return user
