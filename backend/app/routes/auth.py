from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import (
    create_session,
    derive_display_name,
    get_current_user_optional,
    get_current_user_required,
    get_db,
    hash_password,
    normalize_email,
    verify_password,
)
from app.models import AuthSession, UserAccount
from app.routes.billing import get_user_premium_payload

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=8, max_length=120)


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=8, max_length=120)


class LogoutRequest(BaseModel):
    token: str = Field(..., min_length=20, max_length=255)


@router.post("/register")
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    email = normalize_email(payload.email)
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Enter a valid email address.")
    existing = db.query(UserAccount).filter(UserAccount.email == email).first()
    if existing:
        raise HTTPException(status_code=409, detail="An account with that email already exists.")

    now = datetime.utcnow()
    user = UserAccount(
        email=email,
        display_name=derive_display_name(email),
        password_hash=hash_password(payload.password),
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    db.flush()
    token = create_session(db, user)
    db.commit()
    return {
        "ok": True,
        "token": token,
        "user": {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            **get_user_premium_payload(db, user),
        },
    }


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    email = normalize_email(payload.email)
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Enter a valid email address.")
    user = db.query(UserAccount).filter(UserAccount.email == email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account is inactive.")

    token = create_session(db, user)
    user.updated_at = datetime.utcnow()
    db.add(user)
    db.commit()
    return {
        "ok": True,
        "token": token,
        "user": {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            **get_user_premium_payload(db, user),
        },
    }


@router.get("/me")
def me(user: UserAccount | None = Depends(get_current_user_optional), db: Session = Depends(get_db)):
    if not user:
        return {"authenticated": False, "user": None}
    return {
        "authenticated": True,
        "user": {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            **get_user_premium_payload(db, user),
        },
    }


@router.post("/logout")
def logout(payload: LogoutRequest, user: UserAccount = Depends(get_current_user_required), db: Session = Depends(get_db)):
    session = db.query(AuthSession).filter(
        AuthSession.token == payload.token,
        AuthSession.user_id == user.id,
        AuthSession.revoked_at.is_(None),
    ).first()
    if session:
        session.revoked_at = datetime.utcnow()
        db.add(session)
        db.commit()
    return {"ok": True}
