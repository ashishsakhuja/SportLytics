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

DEFAULT_PRICE_CENTS = 699
DEFAULT_CURRENCY = "usd"
DEFAULT_PLAN_CODE = "pulse_premium_monthly"


def _utcnow() -> datetime:
    return datetime.utcnow()


def _to_datetime(ts: int | float | None) -> datetime | None:
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)


def _obj_get(obj, key: str, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    try:
        value = obj.get(key, default)
        if value is not None:
            return value
    except Exception:
        pass
    return getattr(obj, key, default)


def _first_subscription_item(subscription_obj):
    items = _obj_get(subscription_obj, "items")
    data = _obj_get(items, "data", []) or []
    if data:
        return data[0]
    return None


def _subscription_period_start(subscription_obj):
    top = _obj_get(subscription_obj, "current_period_start")
    if top:
        return top
    item = _first_subscription_item(subscription_obj)
    return _obj_get(item, "current_period_start")


def _subscription_period_end(subscription_obj):
    top = _obj_get(subscription_obj, "current_period_end")
    if top:
        return top
    item = _first_subscription_item(subscription_obj)
    return _obj_get(item, "current_period_end")


def _parse_env_expiration(raw_value: str) -> datetime | None:
    raw = (raw_value or "").strip()
    if not raw:
        return None

    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "SPORTLYTICS_PREMIUM_ADMIN_KEY_EXPIRES_AT is invalid. "
                "Use ISO format like 2026-04-01 or 2026-04-01T23:59:59Z."
            ),
        ) from exc

    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _get_stripe_settings() -> dict[str, str]:
    secret_key = os.getenv("STRIPE_SECRET_KEY", "").strip()
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
    price_id = os.getenv("STRIPE_PRICE_ID", "").strip()
    app_base_url = os.getenv("SPORTLYTICS_APP_BASE_URL", "http://localhost:3000").rstrip("/")

    return {
        "secret_key": secret_key,
        "webhook_secret": webhook_secret,
        "price_id": price_id,
        "app_base_url": app_base_url,
    }


def _require_stripe_secret_key() -> str:
    secret_key = _get_stripe_settings()["secret_key"]
    if not secret_key:
        raise HTTPException(status_code=503, detail="STRIPE_SECRET_KEY is missing on the server.")
    if not secret_key.startswith("sk_"):
        raise HTTPException(
            status_code=503,
            detail="STRIPE_SECRET_KEY must be a Stripe secret key starting with sk_.",
        )
    stripe.api_key = secret_key
    return secret_key


def _require_checkout_config() -> dict[str, str]:
    settings = _get_stripe_settings()
    secret_key = settings["secret_key"]
    price_id = settings["price_id"]

    if not secret_key:
        raise HTTPException(status_code=503, detail="STRIPE_SECRET_KEY is missing on the server.")
    if not secret_key.startswith("sk_"):
        raise HTTPException(
            status_code=503,
            detail="STRIPE_SECRET_KEY must be a Stripe secret key starting with sk_.",
        )
    if not price_id:
        raise HTTPException(status_code=503, detail="STRIPE_PRICE_ID is missing on the server.")
    if not price_id.startswith("price_"):
        raise HTTPException(
            status_code=503,
            detail="STRIPE_PRICE_ID must be a Stripe price id starting with price_.",
        )

    stripe.api_key = secret_key
    return settings


def _get_or_create_subscription(db: Session, user_id: int) -> PremiumSubscription:
    sub = db.query(PremiumSubscription).filter(PremiumSubscription.user_id == user_id).first()
    if sub:
        return sub
    sub = PremiumSubscription(
        user_id=user_id,
        plan_code=DEFAULT_PLAN_CODE,
        status="inactive",
        access_source="stripe",
        price_cents=DEFAULT_PRICE_CENTS,
        currency=DEFAULT_CURRENCY,
        started_at=None,
        ended_at=None,
    )
    db.add(sub)
    db.flush()
    return sub


def _serialize_subscription(sub: PremiumSubscription | None) -> dict:
    return {
        "is_premium": premium_is_active(sub),
        "plan_code": getattr(sub, "plan_code", DEFAULT_PLAN_CODE),
        "status": getattr(sub, "status", None),
        "access_source": getattr(sub, "access_source", None),
        "price_cents": getattr(sub, "price_cents", DEFAULT_PRICE_CENTS if sub else DEFAULT_PRICE_CENTS),
        "currency": getattr(sub, "currency", DEFAULT_CURRENCY if sub else DEFAULT_CURRENCY),
        "current_period_end": getattr(sub, "current_period_end", None).isoformat() if getattr(sub, "current_period_end", None) else None,
        "cancel_at_period_end": bool(getattr(sub, "cancel_at_period_end", False)),
        "stripe_customer_id": getattr(sub, "stripe_customer_id", None),
    }


def _sync_from_stripe_obj(
    db: Session,
    *,
    user: UserAccount | None = None,
    customer_id: str | None = None,
    subscription_obj=None,
    checkout_session_id: str | None = None,
):
    target_user = user

    if target_user is None and subscription_obj is not None:
        metadata = _obj_get(subscription_obj, "metadata", {}) or {}
        user_id = metadata.get("sportlytics_user_id") or metadata.get("user_id")
        if user_id:
            try:
                target_user = db.get(UserAccount, int(user_id))
            except (TypeError, ValueError):
                target_user = None

    if target_user is None and customer_id:
        sub = db.query(PremiumSubscription).filter(PremiumSubscription.stripe_customer_id == customer_id).first()
        if sub:
            target_user = db.get(UserAccount, sub.user_id)

    if target_user is None:
        return None

    sub = _get_or_create_subscription(db, target_user.id)
    sub.plan_code = DEFAULT_PLAN_CODE
    sub.access_source = "stripe"
    sub.price_cents = DEFAULT_PRICE_CENTS
    sub.currency = DEFAULT_CURRENCY

    if customer_id:
        sub.stripe_customer_id = customer_id
    if checkout_session_id:
        sub.stripe_checkout_session_id = checkout_session_id

    if subscription_obj is not None:
        stripe_subscription_id = _obj_get(subscription_obj, "id")
        stripe_status = _obj_get(subscription_obj, "status")
        current_period_end = _subscription_period_end(subscription_obj)
        cancel_at_period_end = _obj_get(subscription_obj, "cancel_at_period_end", False)
        current_period_start = _subscription_period_start(subscription_obj)
        cancel_at = _obj_get(subscription_obj, "cancel_at")

        if stripe_subscription_id:
            sub.stripe_subscription_id = stripe_subscription_id

        if stripe_status:
            sub.status = stripe_status

        period_end_dt = _to_datetime(current_period_end)
        if period_end_dt is not None:
            sub.current_period_end = period_end_dt

        sub.cancel_at_period_end = bool(cancel_at_period_end)

        period_start_dt = _to_datetime(current_period_start)
        if sub.started_at is None and period_start_dt is not None:
            sub.started_at = period_start_dt
        elif sub.started_at is None:
            sub.started_at = _utcnow()

        if sub.status in {"canceled", "unpaid", "incomplete_expired"}:
            sub.ended_at = _to_datetime(cancel_at) or sub.current_period_end or _utcnow()
        else:
            sub.ended_at = None

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
    settings = _require_checkout_config()
    app_base_url = settings["app_base_url"]
    price_id = settings["price_id"]

    local_sub = _get_or_create_subscription(db, user.id)
    if premium_is_active(local_sub) and local_sub.access_source == "admin":
        raise HTTPException(status_code=400, detail="This account already has complimentary premium access.")

    customer_id = local_sub.stripe_customer_id
    if not customer_id:
        customer = stripe.Customer.create(
            email=user.email,
            name=user.display_name,
            metadata={"sportlytics_user_id": str(user.id), "user_id": str(user.id)},
        )
        customer_id = customer.id
        local_sub.stripe_customer_id = customer_id

    local_sub.plan_code = DEFAULT_PLAN_CODE
    local_sub.price_cents = DEFAULT_PRICE_CENTS
    local_sub.currency = DEFAULT_CURRENCY
    local_sub.updated_at = _utcnow()
    db.add(local_sub)
    db.commit()

    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{app_base_url}/dashboard/premium?checkout=success&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{app_base_url}/dashboard/premium?checkout=cancelled",
        allow_promotion_codes=True,
        billing_address_collection="auto",
        client_reference_id=str(user.id),
        metadata={"sportlytics_user_id": str(user.id), "user_id": str(user.id), "plan_code": DEFAULT_PLAN_CODE},
        subscription_data={
            "metadata": {
                "sportlytics_user_id": str(user.id),
                "user_id": str(user.id),
                "plan_code": DEFAULT_PLAN_CODE,
            }
        },
    )
    local_sub.stripe_checkout_session_id = session.id
    local_sub.updated_at = _utcnow()
    db.add(local_sub)
    db.commit()
    return {"ok": True, "url": session.url}


@router.post("/portal-session")
def create_portal_session(user: UserAccount = Depends(get_current_user_required), db: Session = Depends(get_db)):
    settings = _get_stripe_settings()
    _require_stripe_secret_key()

    sub = db.query(PremiumSubscription).filter(PremiumSubscription.user_id == user.id).first()
    if not sub or not sub.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No Stripe billing profile found for this account.")

    session = stripe.billing_portal.Session.create(
        customer=sub.stripe_customer_id,
        return_url=f"{settings['app_base_url']}/dashboard/premium",
    )
    return {"ok": True, "url": session.url}


@router.post("/admin-access")
def redeem_admin_access(payload: AdminAccessRequest, user: UserAccount = Depends(get_current_user_required), db: Session = Depends(get_db)):
    admin_access_key = os.getenv("SPORTLYTICS_PREMIUM_ADMIN_KEY", "").strip()
    admin_access_key_expires_at = os.getenv("SPORTLYTICS_PREMIUM_ADMIN_KEY_EXPIRES_AT", "").strip()

    if not admin_access_key:
        raise HTTPException(status_code=503, detail="Admin access keys are not configured on the server.")

    key_expires_at = _parse_env_expiration(admin_access_key_expires_at)
    now = _utcnow()
    if key_expires_at and key_expires_at <= now:
        raise HTTPException(status_code=403, detail="This admin access key has expired.")

    provided = payload.admin_key.strip().encode("utf-8")
    expected = admin_access_key.encode("utf-8")
    if not hmac.compare_digest(hashlib.sha256(provided).digest(), hashlib.sha256(expected).digest()):
        raise HTTPException(status_code=403, detail="Invalid admin access key.")

    sub = _get_or_create_subscription(db, user.id)
    sub.plan_code = DEFAULT_PLAN_CODE
    sub.status = "complimentary"
    sub.access_source = "admin"
    sub.price_cents = 0
    sub.currency = DEFAULT_CURRENCY
    sub.cancel_at_period_end = False
    sub.started_at = now
    sub.current_period_end = key_expires_at
    sub.ended_at = None
    sub.updated_at = now
    db.add(sub)
    db.commit()
    return {"ok": True, "subscription": _serialize_subscription(sub)}


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
    db: Session = Depends(get_db),
):
    settings = _get_stripe_settings()
    secret_key = settings["secret_key"]
    webhook_secret = settings["webhook_secret"]

    if not secret_key:
        raise HTTPException(status_code=503, detail="STRIPE_SECRET_KEY is missing on the server.")
    if not secret_key.startswith("sk_"):
        raise HTTPException(status_code=503, detail="STRIPE_SECRET_KEY must start with sk_.")
    if not webhook_secret:
        raise HTTPException(status_code=503, detail="STRIPE_WEBHOOK_SECRET is missing on the server.")
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header.")

    stripe.api_key = secret_key
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(payload=payload, sig_header=stripe_signature, secret=webhook_secret)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid Stripe webhook payload: {exc}") from exc
    except stripe.error.SignatureVerificationError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid Stripe webhook signature: {exc}") from exc

    event_type = event.get("type")
    data = (event.get("data") or {}).get("object") or {}

    if event_type == "checkout.session.completed":
        customer_id = data.get("customer")
        subscription_id = data.get("subscription")
        user_id = (
            (data.get("metadata") or {}).get("sportlytics_user_id")
            or (data.get("metadata") or {}).get("user_id")
            or data.get("client_reference_id")
        )
        user = None
        if user_id:
            try:
                user = db.get(UserAccount, int(user_id))
            except (TypeError, ValueError):
                user = None

        sub_obj = stripe.Subscription.retrieve(subscription_id) if subscription_id else None
        _sync_from_stripe_obj(
            db,
            user=user,
            customer_id=customer_id,
            subscription_obj=sub_obj,
            checkout_session_id=data.get("id"),
        )
        db.commit()

    elif event_type in {"customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"}:
        _sync_from_stripe_obj(db, customer_id=data.get("customer"), subscription_obj=data)
        db.commit()

    elif event_type in {"invoice.paid", "invoice.payment_succeeded"}:
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
