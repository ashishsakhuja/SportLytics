from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import os

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user_required, get_db
from app.models import PremiumSubscription, UserAccount, premium_is_active

router = APIRouter(prefix="/billing", tags=["billing"])

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID", "").strip()
APP_BASE_URL = os.getenv("SPORTLYTICS_APP_BASE_URL", "http://localhost:3000").rstrip("/")
ADMIN_ACCESS_KEY = os.getenv("SPORTLYTICS_PREMIUM_ADMIN_KEY", "").strip()

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY


def _utcnow() -> datetime:
    return datetime.utcnow()


def _to_datetime(ts: int | float | None) -> datetime | None:
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)


def _get_or_create_subscription(db: Session, user_id: int) -> PremiumSubscription:
    sub = db.query(PremiumSubscription).filter(PremiumSubscription.user_id == user_id).first()
    if sub:
        return sub
    sub = PremiumSubscription(user_id=user_id, status="inactive", access_source="stripe", started_at=None, ended_at=None)
    db.add(sub)
    db.flush()
    return sub


def _serialize_subscription(sub: PremiumSubscription | None) -> dict:
    return {
        "is_premium": premium_is_active(sub),
        "plan_code": getattr(sub, "plan_code", None),
        "status": getattr(sub, "status", None),
        "access_source": getattr(sub, "access_source", None),
        "price_cents": getattr(sub, "price_cents", 499 if sub else 499),
        "currency": getattr(sub, "currency", "usd" if sub else "usd"),
        "current_period_end": getattr(sub, "current_period_end", None).isoformat() if getattr(sub, "current_period_end", None) else None,
        "cancel_at_period_end": bool(getattr(sub, "cancel_at_period_end", False)),
        "stripe_customer_id": getattr(sub, "stripe_customer_id", None),
    }


def _sync_from_stripe_obj(db: Session, *, user: UserAccount | None = None, customer_id: str | None = None, subscription_obj=None, checkout_session_id: str | None = None):
    target_user = user
    if target_user is None and subscription_obj is not None:
        metadata = getattr(subscription_obj, "metadata", None) or {}
        user_id = metadata.get("sportlytics_user_id")
        if user_id:
            target_user = db.get(UserAccount, int(user_id))
    if target_user is None and customer_id:
        sub = db.query(PremiumSubscription).filter(PremiumSubscription.stripe_customer_id == customer_id).first()
        if sub:
            target_user = db.get(UserAccount, sub.user_id)
    if target_user is None:
        return None

    sub = _get_or_create_subscription(db, target_user.id)
    sub.access_source = "stripe"
    if customer_id:
        sub.stripe_customer_id = customer_id
    if checkout_session_id:
        sub.stripe_checkout_session_id = checkout_session_id
    if subscription_obj is not None:
        sub.stripe_subscription_id = getattr(subscription_obj, "id", None)
        sub.status = getattr(subscription_obj, "status", None) or sub.status
        sub.current_period_end = _to_datetime(getattr(subscription_obj, "current_period_end", None))
        sub.cancel_at_period_end = bool(getattr(subscription_obj, "cancel_at_period_end", False))
        if sub.started_at is None:
            sub.started_at = _utcnow()
        if sub.status not in {"active", "trialing", "past_due", "incomplete"}:
            sub.ended_at = _utcnow()
    sub.updated_at = _utcnow()
    db.add(sub)
    db.flush()
    return sub


def get_user_premium_payload(db: Session, user: UserAccount) -> dict:
    sub = db.query(PremiumSubscription).filter(PremiumSubscription.user_id == user.id).first()
    return _serialize_subscription(sub)


class AdminAccessRequest(BaseModel):
    admin_key: str = Field(..., min_length=6, max_length=255)


@router.get("/me")
def billing_me(user: UserAccount = Depends(get_current_user_required), db: Session = Depends(get_db)):
    return {"ok": True, "subscription": get_user_premium_payload(db, user)}


@router.post("/checkout-session")
def create_checkout_session(user: UserAccount = Depends(get_current_user_required), db: Session = Depends(get_db)):
    if not STRIPE_SECRET_KEY or not STRIPE_PRICE_ID:
        raise HTTPException(status_code=503, detail="Stripe billing is not configured on the server.")

    local_sub = _get_or_create_subscription(db, user.id)
    if premium_is_active(local_sub) and local_sub.access_source == "admin":
        raise HTTPException(status_code=400, detail="This account already has complimentary premium access.")

    customer_id = local_sub.stripe_customer_id
    if not customer_id:
        customer = stripe.Customer.create(
            email=user.email,
            name=user.display_name,
            metadata={"sportlytics_user_id": str(user.id)},
        )
        customer_id = customer.id
        local_sub.stripe_customer_id = customer_id
        local_sub.updated_at = _utcnow()
        db.add(local_sub)
        db.commit()

    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
        success_url=f"{APP_BASE_URL}/dashboard/premium?checkout=success",
        cancel_url=f"{APP_BASE_URL}/dashboard/premium?checkout=cancelled",
        allow_promotion_codes=True,
        billing_address_collection="auto",
        client_reference_id=str(user.id),
        metadata={"sportlytics_user_id": str(user.id), "plan_code": "pulse_premium_monthly"},
    )
    local_sub.stripe_checkout_session_id = session.id
    local_sub.updated_at = _utcnow()
    db.add(local_sub)
    db.commit()
    return {"ok": True, "url": session.url}


@router.post("/portal-session")
def create_portal_session(user: UserAccount = Depends(get_current_user_required), db: Session = Depends(get_db)):
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe billing is not configured on the server.")
    sub = db.query(PremiumSubscription).filter(PremiumSubscription.user_id == user.id).first()
    if not sub or not sub.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No Stripe billing profile found for this account.")
    session = stripe.billing_portal.Session.create(
        customer=sub.stripe_customer_id,
        return_url=f"{APP_BASE_URL}/dashboard/premium",
    )
    return {"ok": True, "url": session.url}


@router.post("/admin-access")
def redeem_admin_access(payload: AdminAccessRequest, user: UserAccount = Depends(get_current_user_required), db: Session = Depends(get_db)):
    if not ADMIN_ACCESS_KEY:
        raise HTTPException(status_code=503, detail="Admin access keys are not configured on the server.")

    provided = payload.admin_key.strip().encode("utf-8")
    expected = ADMIN_ACCESS_KEY.encode("utf-8")
    if not hmac.compare_digest(hashlib.sha256(provided).digest(), hashlib.sha256(expected).digest()):
        raise HTTPException(status_code=403, detail="Invalid admin access key.")

    sub = _get_or_create_subscription(db, user.id)
    sub.plan_code = "pulse_premium_monthly"
    sub.status = "complimentary"
    sub.access_source = "admin"
    sub.price_cents = 0
    sub.currency = "usd"
    sub.cancel_at_period_end = False
    sub.started_at = sub.started_at or _utcnow()
    sub.current_period_end = None
    sub.ended_at = None
    sub.updated_at = _utcnow()
    db.add(sub)
    db.commit()
    return {"ok": True, "subscription": _serialize_subscription(sub)}


@router.post("/webhook")
async def stripe_webhook(request: Request, stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"), db: Session = Depends(get_db)):
    if not STRIPE_SECRET_KEY or not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Stripe webhook is not configured.")

    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(payload=payload, sig_header=stripe_signature, secret=STRIPE_WEBHOOK_SECRET)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid Stripe webhook: {exc}")

    event_type = event.get("type")
    data = (event.get("data") or {}).get("object") or {}

    if event_type == "checkout.session.completed":
        customer_id = data.get("customer")
        subscription_id = data.get("subscription")
        user_id = ((data.get("metadata") or {}).get("sportlytics_user_id") or data.get("client_reference_id"))
        user = db.get(UserAccount, int(user_id)) if user_id else None
        sub_obj = None
        if subscription_id:
            sub_obj = stripe.Subscription.retrieve(subscription_id)
        _sync_from_stripe_obj(db, user=user, customer_id=customer_id, subscription_obj=sub_obj, checkout_session_id=data.get("id"))
        db.commit()
    elif event_type in {"customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"}:
        _sync_from_stripe_obj(db, customer_id=data.get("customer"), subscription_obj=data)
        db.commit()
    elif event_type == "invoice.paid":
        subscription_id = data.get("subscription")
        if subscription_id:
            sub_obj = stripe.Subscription.retrieve(subscription_id)
            _sync_from_stripe_obj(db, customer_id=data.get("customer"), subscription_obj=sub_obj)
            db.commit()
    elif event_type == "invoice.payment_failed":
        sub = db.query(PremiumSubscription).filter(PremiumSubscription.stripe_customer_id == data.get("customer")).first()
        if sub:
            sub.status = "past_due"
            sub.updated_at = _utcnow()
            db.add(sub)
            db.commit()

    return {"ok": True}
