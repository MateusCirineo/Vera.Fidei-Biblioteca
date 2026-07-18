from __future__ import annotations

import datetime
import secrets
from typing import Any

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from core.auth import require_api_key
from core.config import settings
from core.deps import get_current_user
from core.plans import ensure_owner_access, is_owner_email
from models.database import BillingRequest, SessionLocal, User

router = APIRouter()

PAID_PLANS = {"catequista", "apologeta", "patristico", "magisterio"}
ACTIVE_BILLING_STATUSES = {"active", "trialing"}

PLAN_NAMES = {
    "catequista": "Catequista",
    "apologeta": "Apologeta",
    "patristico": "Patrístico",
    "magisterio": "Magistério",
}

PLAN_PRICE_SETTINGS = {
    "catequista": "stripe_price_catequista",
    "apologeta": "stripe_price_apologeta",
    "patristico": "stripe_price_patristico",
    "magisterio": "stripe_price_magisterio",
}

PLAN_AMOUNTS_CENTS = {
    "catequista": 990,
    "apologeta": 2999,
    "patristico": 5999,
    "magisterio": 9999,
}


class CheckoutRequest(BaseModel):
    plan: str = Field(..., min_length=3, max_length=30)
    coupon_code: str | None = Field(default=None, max_length=50)


class BillingUrlResponse(BaseModel):
    url: str


class PixRequestResponse(BaseModel):
    reference_code: str
    plan: str
    plan_name: str
    amount_cents: int
    amount_label: str
    status: str
    recipient_name: str
    recipient_bank: str
    pix_key: str
    pix_payload: str | None = None
    created_at: datetime.datetime


class AdminCouponResponse(BaseModel):
    id: str
    code: str
    active: bool
    status: str
    status_label: str
    percent_off: float | None = None
    amount_off: int | None = None
    currency: str | None = None
    duration: str | None = None
    times_redeemed: int
    max_redemptions: int | None = None
    created_at: datetime.datetime | None = None


class AdminCouponsResponse(BaseModel):
    mode: str
    prefix: str
    total: int
    available_count: int
    used_count: int
    inactive_count: int
    available: list[AdminCouponResponse]
    used: list[AdminCouponResponse]
    inactive: list[AdminCouponResponse]


def _site_url() -> str:
    return settings.site_url.rstrip("/")


def _amount_label(amount_cents: int) -> str:
    return f"R$ {amount_cents / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _stripe_ready_for_plan(plan: str) -> bool:
    return bool(
        settings.billing_provider == "stripe"
        and settings.stripe_secret_key
        and getattr(settings, PLAN_PRICE_SETTINGS.get(plan, ""), "")
    )


def _stripe_get(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    try:
        return obj.get(key, default)
    except AttributeError:
        pass
    try:
        return obj[key]
    except (KeyError, TypeError):
        return default


def _resolve_promotion_code(code: str) -> str | None:
    results = stripe.PromotionCode.list(code=code.strip().upper(), active=True, limit=1)
    items = (_stripe_get(results, "data") or [])
    return _stripe_get(items[0], "id") if items else None


def _configure_stripe() -> None:
    if settings.billing_provider != "stripe":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Provedor de cobrança não configurado.",
        )
    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe ainda não configurado. Defina STRIPE_SECRET_KEY e os price IDs mensais.",
        )
    stripe.api_key = settings.stripe_secret_key


def _require_owner_admin(current_user: User) -> None:
    if not is_owner_email(current_user.email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito ao administrador do Vera.Fidei.",
        )


def _payment_method_types() -> list[str] | None:
    values = [
        item.strip()
        for item in settings.stripe_payment_method_types.split(",")
        if item.strip()
    ]
    return values or None


def _price_id_for_plan(plan: str) -> str:
    setting_name = PLAN_PRICE_SETTINGS.get(plan)
    price_id = getattr(settings, setting_name, "") if setting_name else ""
    if not price_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Preço mensal do plano {PLAN_NAMES.get(plan, plan)} ainda não configurado.",
        )
    return price_id


def _new_reference(user_id: int) -> str:
    stamp = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return f"VF-{user_id}-{stamp}-{secrets.token_hex(3).upper()}"


def _create_manual_pix_request(db, user: User, plan: str) -> BillingRequest:
    billing_request = BillingRequest(
        user_id=user.id,
        plan=plan,
        amount_cents=PLAN_AMOUNTS_CENTS[plan],
        status="pending",
        provider="manual_pix",
        reference_code=_new_reference(user.id),
    )
    user.billing_provider = "manual_pix"
    user.billing_status = "pending_payment"
    user.billing_subscription_id = billing_request.reference_code
    user.billing_cancel_at_period_end = False
    db.add(billing_request)
    db.commit()
    db.refresh(billing_request)
    return billing_request


def _plan_from_price_id(price_id: str | None) -> str | None:
    if not price_id:
        return None
    for plan, setting_name in PLAN_PRICE_SETTINGS.items():
        if price_id == getattr(settings, setting_name, ""):
            return plan
    return None


def _timestamp_to_datetime(value: Any) -> datetime.datetime | None:
    if not value:
        return None
    try:
        return datetime.datetime.fromtimestamp(int(value), datetime.timezone.utc).replace(tzinfo=None)
    except (TypeError, ValueError, OSError):
        return None


def _coupon_payload_from_promotion_code(
    item: Any,
    coupon_cache: dict[str, Any] | None = None,
) -> AdminCouponResponse:
    promotion = _stripe_get(item, "promotion") or {}
    coupon = _stripe_get(item, "coupon") or _stripe_get(promotion, "coupon") or {}
    if isinstance(coupon, str):
        if coupon_cache is not None and coupon in coupon_cache:
            coupon = coupon_cache[coupon]
        else:
            coupon_obj = stripe.Coupon.retrieve(coupon)
            if coupon_cache is not None:
                coupon_cache[coupon] = coupon_obj
            coupon = coupon_obj

    max_redemptions = _stripe_get(item, "max_redemptions")
    times_redeemed = int(_stripe_get(item, "times_redeemed", 0) or 0)
    active = bool(_stripe_get(item, "active"))
    exhausted = max_redemptions is not None and times_redeemed >= int(max_redemptions)

    if active and not exhausted:
        status_value = "available"
        status_label = "Disponivel"
    elif exhausted:
        status_value = "used"
        status_label = "Usado"
    else:
        status_value = "inactive"
        status_label = "Inativo"

    return AdminCouponResponse(
        id=_stripe_get(item, "id"),
        code=_stripe_get(item, "code"),
        active=active,
        status=status_value,
        status_label=status_label,
        percent_off=_stripe_get(coupon, "percent_off"),
        amount_off=_stripe_get(coupon, "amount_off"),
        currency=_stripe_get(coupon, "currency"),
        duration=_stripe_get(coupon, "duration"),
        times_redeemed=times_redeemed,
        max_redemptions=max_redemptions,
        created_at=_timestamp_to_datetime(_stripe_get(item, "created")),
    )


def _ensure_customer(db, user: User) -> str:
    if user.billing_customer_id:
        return user.billing_customer_id
    customer = stripe.Customer.create(
        email=user.email,
        name=user.name,
        metadata={"user_id": str(user.id)},
    )
    user.billing_provider = "stripe"
    user.billing_customer_id = customer["id"]
    db.commit()
    db.refresh(user)
    return user.billing_customer_id


def _portal_url(customer_id: str) -> str:
    session_args = {
        "customer": customer_id,
        "return_url": f"{_site_url()}/perfil?assinatura=portal",
    }
    if settings.stripe_portal_configuration_id:
        session_args["configuration"] = settings.stripe_portal_configuration_id
    session = stripe.billing_portal.Session.create(**session_args)
    return session["url"]


def _subscription_plan(subscription: Any, fallback_plan: str | None = None) -> str | None:
    metadata = subscription.get("metadata") or {}
    plan = metadata.get("plan") or fallback_plan
    if plan in PAID_PLANS:
        return plan

    items = ((subscription.get("items") or {}).get("data") or [])
    if items:
        price = (items[0].get("price") or {})
        plan = _plan_from_price_id(price.get("id"))
        if plan in PAID_PLANS:
            return plan
    return None


def _find_user(db, *, user_id: str | None, customer_id: str | None, subscription_id: str | None) -> User | None:
    if user_id and user_id.isdigit():
        user = db.get(User, int(user_id))
        if user:
            return user
    if subscription_id:
        user = db.query(User).filter(User.billing_subscription_id == subscription_id).first()
        if user:
            return user
    if customer_id:
        user = db.query(User).filter(User.billing_customer_id == customer_id).first()
        if user:
            return user
    return None


def _apply_subscription(db, user: User, subscription: Any, fallback_plan: str | None = None) -> None:
    plan = _subscription_plan(subscription, fallback_plan=fallback_plan)
    status_value = subscription.get("status")
    customer_id = subscription.get("customer")
    subscription_id = subscription.get("id")

    user.billing_provider = "stripe"
    if customer_id:
        user.billing_customer_id = customer_id
    if subscription_id:
        user.billing_subscription_id = subscription_id
    user.billing_status = status_value
    user.billing_current_period_end = _timestamp_to_datetime(subscription.get("current_period_end"))
    user.billing_cancel_at_period_end = bool(subscription.get("cancel_at_period_end"))

    if ensure_owner_access(user):
        return

    if status_value in ACTIVE_BILLING_STATUSES and plan in PAID_PLANS:
        user.plan = plan
    elif status_value in {"canceled", "incomplete_expired", "unpaid"}:
        user.plan = "fiel"


@router.post("/checkout", response_model=BillingUrlResponse, dependencies=[Depends(require_api_key)])
def create_checkout_session(
    payload: CheckoutRequest,
    current_user: User = Depends(get_current_user),
) -> BillingUrlResponse:
    plan = payload.plan.strip().lower()
    if plan not in PAID_PLANS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Plano inválido.")
    if is_owner_email(current_user.email):
        return BillingUrlResponse(url=f"{_site_url()}/perfil?assinatura=owner")

    with SessionLocal() as db:
        user = db.get(User, current_user.id)
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário não encontrado.")

        if not _stripe_ready_for_plan(plan):
            billing_request = _create_manual_pix_request(db, user, plan)
            return BillingUrlResponse(
                url=f"{_site_url()}/assinatura/pix?ref={billing_request.reference_code}"
            )

        _configure_stripe()

        customer_id = _ensure_customer(db, user)

        if user.billing_subscription_id and user.billing_status in ACTIVE_BILLING_STATUSES:
            return BillingUrlResponse(url=_portal_url(customer_id))

        price_id = _price_id_for_plan(plan)
        session_args: dict[str, Any] = {
            "mode": "subscription",
            "customer": customer_id,
            "client_reference_id": str(user.id),
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": f"{_site_url()}/perfil?assinatura=sucesso",
            "cancel_url": f"{_site_url()}/planos?assinatura=cancelada",
            "metadata": {"user_id": str(user.id), "plan": plan},
            "subscription_data": {"metadata": {"user_id": str(user.id), "plan": plan}},
        }

        raw_coupon = (payload.coupon_code or "").strip()
        if raw_coupon:
            promo_id = _resolve_promotion_code(raw_coupon)
            if not promo_id:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Cupom inválido ou já utilizado.",
                )
            session_args["discounts"] = [{"promotion_code": promo_id}]
        else:
            session_args["allow_promotion_codes"] = True
        payment_methods = _payment_method_types()
        if payment_methods:
            session_args["payment_method_types"] = payment_methods

        try:
            checkout = stripe.checkout.Session.create(**session_args)
        except stripe.error.StripeError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return BillingUrlResponse(url=checkout["url"])


@router.get("/pix/{reference_code}", response_model=PixRequestResponse, dependencies=[Depends(require_api_key)])
def get_pix_request(
    reference_code: str,
    current_user: User = Depends(get_current_user),
) -> PixRequestResponse:
    with SessionLocal() as db:
        billing_request = (
            db.query(BillingRequest)
            .filter(BillingRequest.reference_code == reference_code)
            .first()
        )
        if not billing_request or billing_request.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assinatura Pix não encontrada.")

        return PixRequestResponse(
            reference_code=billing_request.reference_code,
            plan=billing_request.plan,
            plan_name=PLAN_NAMES.get(billing_request.plan, billing_request.plan),
            amount_cents=billing_request.amount_cents,
            amount_label=_amount_label(billing_request.amount_cents),
            status=billing_request.status,
            recipient_name=settings.billing_recipient_name,
            recipient_bank=settings.billing_recipient_bank,
            pix_key=settings.billing_recipient_pix_key,
            pix_payload=settings.billing_pix_payload or None,
            created_at=billing_request.created_at,
        )


@router.post("/portal", response_model=BillingUrlResponse, dependencies=[Depends(require_api_key)])
def create_portal_session(current_user: User = Depends(get_current_user)) -> BillingUrlResponse:
    if is_owner_email(current_user.email):
        return BillingUrlResponse(url=f"{_site_url()}/perfil?assinatura=owner")
    _configure_stripe()

    with SessionLocal() as db:
        user = db.get(User, current_user.id)
        if not user or not user.billing_customer_id:
            raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhuma assinatura encontrada para gerenciar.",
            )
        try:
            return BillingUrlResponse(url=_portal_url(user.billing_customer_id))
        except stripe.error.StripeError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.get("/admin/coupons", response_model=AdminCouponsResponse, dependencies=[Depends(require_api_key)])
def list_admin_coupons(
    prefix: str = Query(default="COLEGIO", max_length=40),
    limit: int = Query(default=100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
) -> AdminCouponsResponse:
    _require_owner_admin(current_user)
    _configure_stripe()

    clean_prefix = prefix.strip().upper()
    mode = "teste" if settings.stripe_secret_key.startswith("sk_test_") else "producao"

    try:
        collected: list[AdminCouponResponse] = []
        coupon_cache: dict[str, Any] = {}
        params: dict[str, Any] = {"limit": min(limit, 100)}
        has_more = True
        starting_after: str | None = None

        while has_more and len(collected) < limit:
            if starting_after:
                params["starting_after"] = starting_after
            page = stripe.PromotionCode.list(**params)
            data = _stripe_get(page, "data") or []
            for item in data:
                code = str(_stripe_get(item, "code") or "").upper()
                if clean_prefix and not code.startswith(clean_prefix):
                    continue
                collected.append(_coupon_payload_from_promotion_code(item, coupon_cache=coupon_cache))
                if len(collected) >= limit:
                    break
            has_more = bool(_stripe_get(page, "has_more")) and bool(data)
            if data:
                starting_after = _stripe_get(data[-1], "id")
            else:
                break
    except stripe.error.StripeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    available = [coupon for coupon in collected if coupon.status == "available"]
    used = [coupon for coupon in collected if coupon.status == "used"]
    inactive = [coupon for coupon in collected if coupon.status == "inactive"]

    return AdminCouponsResponse(
        mode=mode,
        prefix=clean_prefix,
        total=len(collected),
        available_count=len(available),
        used_count=len(used),
        inactive_count=len(inactive),
        available=available,
        used=used,
        inactive=inactive,
    )


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(default="", alias="Stripe-Signature"),
) -> dict[str, bool]:
    if not settings.stripe_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook Stripe ainda não configurado.",
        )
    _configure_stripe()

    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=stripe_signature,
            secret=settings.stripe_webhook_secret,
        )
    except (ValueError, stripe.error.SignatureVerificationError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Webhook inválido.") from exc

    event_type = event["type"]
    data = event["data"]["object"]

    with SessionLocal() as db:
        if event_type == "checkout.session.completed":
            user_id = (data.get("metadata") or {}).get("user_id") or data.get("client_reference_id")
            plan = (data.get("metadata") or {}).get("plan")
            subscription_id = data.get("subscription")
            customer_id = data.get("customer")
            user = _find_user(db, user_id=user_id, customer_id=customer_id, subscription_id=subscription_id)
            if user and subscription_id:
                subscription = stripe.Subscription.retrieve(subscription_id)
                _apply_subscription(db, user, subscription, fallback_plan=plan)
                db.commit()

        elif event_type in {
            "customer.subscription.created",
            "customer.subscription.updated",
            "customer.subscription.deleted",
        }:
            subscription_id = data.get("id")
            customer_id = data.get("customer")
            metadata = data.get("metadata") or {}
            user = _find_user(
                db,
                user_id=metadata.get("user_id"),
                customer_id=customer_id,
                subscription_id=subscription_id,
            )
            if user:
                _apply_subscription(db, user, data, fallback_plan=metadata.get("plan"))
                db.commit()

        elif event_type in {"invoice.payment_succeeded", "invoice.payment_failed"}:
            subscription_id = data.get("subscription")
            customer_id = data.get("customer")
            if subscription_id:
                user = _find_user(db, user_id=None, customer_id=customer_id, subscription_id=subscription_id)
                if user:
                    subscription = stripe.Subscription.retrieve(subscription_id)
                    _apply_subscription(db, user, subscription)
                    db.commit()

    return {"received": True}
