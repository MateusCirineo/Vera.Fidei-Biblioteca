from __future__ import annotations

import datetime
import logging
import secrets
from typing import Any, Literal

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from starlette.concurrency import run_in_threadpool

from core.auth import require_api_key
from core.config import settings
from core.deps import get_current_user
from core.plans import ensure_owner_access, is_owner_email
from models.database import (
    BillingRequest,
    BillingSubscription,
    BillingSubscriptionItem,
    SessionLocal,
    User,
)
from services.billing_entitlements import (
    SubscriptionItemInput,
    has_recoverable_provider_subscription,
    lock_user_for_billing_mutation,
    record_stripe_projection,
    recompute_user_plan,
    upsert_subscription,
)

router = APIRouter()
logger = logging.getLogger(__name__)

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


class BillingSyncResponse(BaseModel):
    synced: bool
    plan: str
    billing_status: str | None = None


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


class AdminCouponCreateRequest(BaseModel):
    code: str = Field(..., min_length=3, max_length=50, pattern=r"^[A-Za-z0-9-]+$")
    percent_off: float = Field(..., gt=0, le=100)
    duration: Literal["once", "forever"] = "once"
    max_redemptions: int | None = Field(default=None, ge=1, le=100000)
    name: str | None = Field(default=None, max_length=100)


def _site_url(request: Request | None = None) -> str:
    """Return only a trusted public origin for browser redirects.

    Session cookies are host-only. During the domain transition, a checkout
    opened on the legacy host must return there or the paid user would appear
    signed out. An arbitrary Host header always falls back to the configured
    canonical URL.
    """
    canonical = settings.site_url.rstrip("/")
    if request is None:
        return canonical

    host = request.headers.get("host", "").split(",", 1)[0].strip().lower()
    if host.endswith(":443"):
        host = host[:-4]
    trusted_returns = {
        "verafidei.com.br": "https://verafidei.com.br",
        # www is redirected to the apex before the application is reached.
        "www.verafidei.com.br": "https://verafidei.com.br",
        "verafidei.oialfred.com": "https://verafidei.oialfred.com",
    }
    return trusted_returns.get(host, canonical)


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


def _stripe_id(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    object_id = _stripe_get(value, "id")
    return str(object_id) if object_id else None


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
        idempotency_key=f"vf-customer-v1-{user.id}",
    )
    user.billing_provider = "stripe"
    user.billing_customer_id = customer["id"]
    db.flush()
    return user.billing_customer_id


def _stripe_page_items(page: Any) -> list[Any]:
    auto_paging_iter = getattr(page, "auto_paging_iter", None)
    if callable(auto_paging_iter):
        return list(auto_paging_iter())
    items = _stripe_get(page, "data") or []
    if not isinstance(items, (list, tuple)):
        raise RuntimeError("Stripe returned an invalid collection response")
    return list(items)


def _mark_checkout_intent_terminal(
    db,
    intent: BillingSubscription,
    status_value: str,
) -> None:
    intent.provider_status = f"checkout_{status_value}"
    intent.entitlement_state = "inactive"
    intent.updated_at = datetime.datetime.utcnow()
    db.query(BillingSubscriptionItem).filter(
        BillingSubscriptionItem.billing_subscription_id == intent.id
    ).update({BillingSubscriptionItem.entitled: False}, synchronize_session=False)
    db.flush()


def _refresh_pending_checkout_intents(db, user: User) -> tuple[bool, bool]:
    """Resolve local checkout intents from Stripe and block every open session."""
    terminal_checkout_found = False
    unresolved_complete_found = False
    intents = (
        db.query(BillingSubscription)
        .filter(
            BillingSubscription.user_id == user.id,
            BillingSubscription.provider == "stripe",
            BillingSubscription.provider_status == "checkout_pending",
            BillingSubscription.entitlement_state == "pending",
        )
        .all()
    )
    for intent in intents:
        checkout_id = (intent.external_subscription_id or "").strip()
        if not checkout_id.startswith("cs_"):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Nao foi possivel confirmar o checkout anterior agora.",
            )
        try:
            checkout = stripe.checkout.Session.retrieve(checkout_id)
        except stripe.error.StripeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Nao foi possivel confirmar o checkout anterior agora.",
            ) from exc
        checkout_status = str(_stripe_get(checkout, "status") or "").strip().lower()
        if checkout_status == "open":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ja existe um checkout Stripe em andamento para esta conta.",
            )
        if checkout_status not in {"complete", "expired"}:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Nao foi possivel confirmar o checkout anterior agora.",
            )
        _mark_checkout_intent_terminal(db, intent, checkout_status)
        terminal_checkout_found = terminal_checkout_found or checkout_status == "complete"
        if checkout_status == "complete" and not _stripe_id(
            _stripe_get(checkout, "subscription")
        ):
            unresolved_complete_found = True
    return terminal_checkout_found, unresolved_complete_found


def _ensure_no_open_checkout_session(customer_id: str) -> None:
    try:
        page = stripe.checkout.Session.list(customer=customer_id, status="open", limit=100)
        open_sessions = _stripe_page_items(page)
    except stripe.error.StripeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Nao foi possivel confirmar checkouts Stripe em andamento.",
        ) from exc
    if open_sessions:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ja existe um checkout Stripe em andamento para esta conta.",
        )


def _checkout_idempotency_key(
    *,
    user_id: int,
    plan: str,
) -> str:
    return f"vf-checkout-v1-{user_id}-{plan}-{secrets.token_hex(16)}"


def _close_checkout_intent_for_event(
    db,
    *,
    user: User,
    checkout_id: str | None,
    event_type: str,
) -> None:
    if not checkout_id:
        return
    intent = (
        db.query(BillingSubscription)
        .filter(
            BillingSubscription.user_id == user.id,
            BillingSubscription.provider == "stripe",
            BillingSubscription.external_subscription_id == checkout_id,
        )
        .one_or_none()
    )
    if intent is None:
        return
    if event_type == "checkout.session.async_payment_failed":
        if intent.provider_status not in {"checkout_pending", "checkout_complete"}:
            return
    elif intent.provider_status not in {"checkout_pending", "checkout_failed"}:
        return
    terminal_status = (
        "failed"
        if event_type == "checkout.session.async_payment_failed"
        else "complete"
    )
    _mark_checkout_intent_terminal(db, intent, terminal_status)


def _portal_url(customer_id: str, request: Request | None = None) -> str:
    session_args = {
        "customer": customer_id,
        "return_url": f"{_site_url(request)}/perfil?assinatura=portal",
    }
    if settings.stripe_portal_configuration_id:
        session_args["configuration"] = settings.stripe_portal_configuration_id
    session = stripe.billing_portal.Session.create(**session_args)
    return session["url"]


def _subscription_plan(subscription: Any, fallback_plan: str | None = None) -> str | None:
    metadata = _stripe_get(subscription, "metadata") or {}
    metadata_plan = _stripe_get(metadata, "plan") or fallback_plan

    items = _stripe_get(_stripe_get(subscription, "items") or {}, "data") or []
    for item in items:
        price = _stripe_get(item, "price") or {}
        plan = _plan_from_price_id(_stripe_id(price))
        if plan in PAID_PLANS:
            return plan
    if items:
        return None
    return metadata_plan if metadata_plan in PAID_PLANS else None


def _subscription_period_end(subscription: Any) -> Any:
    period_end = _stripe_get(subscription, "current_period_end")
    if period_end:
        return period_end

    items = _stripe_get(_stripe_get(subscription, "items") or {}, "data") or []
    item_period_ends = [
        _stripe_get(item, "current_period_end")
        for item in items
        if _stripe_get(item, "current_period_end")
    ]
    return max(item_period_ends) if item_period_ends else None


def _invoice_subscription_id(invoice: Any) -> str | None:
    legacy_id = _stripe_id(_stripe_get(invoice, "subscription"))
    if legacy_id:
        return legacy_id

    parent = _stripe_get(invoice, "parent") or {}
    subscription_details = _stripe_get(parent, "subscription_details") or {}
    parent_id = _stripe_id(_stripe_get(subscription_details, "subscription"))
    if parent_id:
        return parent_id

    lines = _stripe_get(_stripe_get(invoice, "lines") or {}, "data") or []
    for line in lines:
        line_parent = _stripe_get(line, "parent") or {}
        item_details = _stripe_get(line_parent, "subscription_item_details") or {}
        line_id = _stripe_id(_stripe_get(item_details, "subscription"))
        if line_id:
            return line_id
    return None


def _event_email(data: Any) -> str | None:
    customer_details = _stripe_get(data, "customer_details") or {}
    value = (
        _stripe_get(customer_details, "email")
        or _stripe_get(data, "customer_email")
    )
    return str(value).strip().lower() if value else None


def _find_user(
    db,
    *,
    user_id: str | None,
    customer_id: str | None,
    subscription_id: str | None,
    email: str | None = None,
) -> User | None:
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
    if email:
        normalized_email = email.strip().lower()
        user = db.query(User).filter(func.lower(User.email) == normalized_email).first()
        if user:
            return user
    return None


def _apply_subscription(db, user: User, subscription: Any, fallback_plan: str | None = None) -> None:
    plan = _subscription_plan(subscription, fallback_plan=fallback_plan)
    status_value = _stripe_get(subscription, "status")
    customer_id = _stripe_id(_stripe_get(subscription, "customer"))
    subscription_id = _stripe_id(subscription)

    user.billing_provider = "stripe"
    if customer_id:
        user.billing_customer_id = customer_id
    if subscription_id:
        user.billing_subscription_id = subscription_id
    user.billing_status = status_value
    user.billing_current_period_end = _timestamp_to_datetime(_subscription_period_end(subscription))
    user.billing_cancel_at_period_end = bool(_stripe_get(subscription, "cancel_at_period_end"))

    if is_owner_email(user.email):
        ensure_owner_access(user)
        return
    record_stripe_projection(
        db,
        user=user,
        subscription_id=subscription_id,
        customer_id=customer_id,
        status_value=status_value,
        plan=plan,
        current_period_end=user.billing_current_period_end,
        cancel_at_period_end=user.billing_cancel_at_period_end,
    )
    recompute_user_plan(db, user)


def _latest_subscription_for_user(
    user: User,
    *,
    candidate_subscription: Any | None = None,
) -> Any | None:
    """Return the newest authoritative subscription without trusting event order.

    Stripe can retry old events after a newer subscription has already become
    active. Collecting the candidate, the locally linked subscription and the
    customer's current list prevents a late cancellation/failure from
    overwriting a newer paid plan.
    """

    subscriptions_by_id: dict[str, Any] = {}

    def remember(subscription: Any | None) -> None:
        subscription_id = _stripe_id(subscription)
        if subscription_id:
            subscriptions_by_id[subscription_id] = subscription

    remember(candidate_subscription)
    candidate_id = _stripe_id(candidate_subscription)
    subscription_id = user.billing_subscription_id or ""
    if subscription_id.startswith("sub_") and subscription_id != candidate_id:
        try:
            remember(stripe.Subscription.retrieve(subscription_id))
        except stripe.error.InvalidRequestError:
            logger.warning(
                "stripe_subscription_not_found user_id=%s subscription_suffix=%s",
                user.id,
                subscription_id[-8:],
            )

    customer_ids: list[str] = []
    for value in (
        user.billing_customer_id,
        _stripe_id(_stripe_get(candidate_subscription, "customer")),
        *(
            _stripe_id(_stripe_get(subscription, "customer"))
            for subscription in subscriptions_by_id.values()
        ),
    ):
        if value and value not in customer_ids:
            customer_ids.append(value)

    if not customer_ids:
        customers = _stripe_get(stripe.Customer.list(email=user.email, limit=10), "data") or []
        matching_customers = [
            customer
            for customer in customers
            if str(_stripe_get(_stripe_get(customer, "metadata") or {}, "user_id") or "") == str(user.id)
        ]
        customer = matching_customers[0] if matching_customers else (customers[0] if len(customers) == 1 else None)
        customer_id = _stripe_id(customer)
        if customer_id:
            user.billing_provider = "stripe"
            user.billing_customer_id = customer_id
            customer_ids.append(customer_id)

    invalid_customer_ids: list[str] = []

    def load_customer_subscriptions(customer_id: str) -> bool:
        try:
            listed_subscriptions = _stripe_get(
                stripe.Subscription.list(customer=customer_id, status="all", limit=100),
                "data",
            ) or []
        except stripe.error.InvalidRequestError:
            logger.warning(
                "stripe_customer_not_found user_id=%s customer_suffix=%s",
                user.id,
                customer_id[-8:],
            )
            invalid_customer_ids.append(customer_id)
            return False
        for subscription in listed_subscriptions:
            remember(subscription)
        return True

    for customer_id in customer_ids:
        load_customer_subscriptions(customer_id)

    has_active_subscription = any(
        _stripe_get(subscription, "status") in ACTIVE_BILLING_STATUSES
        and _subscription_plan(subscription) in PAID_PLANS
        for subscription in subscriptions_by_id.values()
    )
    if invalid_customer_ids and not has_active_subscription:
        customers = _stripe_get(stripe.Customer.list(email=user.email, limit=10), "data") or []
        replacements = [
            customer
            for customer in customers
            if str(_stripe_get(_stripe_get(customer, "metadata") or {}, "user_id") or "")
            == str(user.id)
            and _stripe_id(customer) not in customer_ids
        ]
        for replacement in replacements:
            replacement_id = _stripe_id(replacement)
            if replacement_id and load_customer_subscriptions(replacement_id):
                user.billing_customer_id = replacement_id

    subscriptions = list(subscriptions_by_id.values())
    eligible = [subscription for subscription in subscriptions if _subscription_plan(subscription) in PAID_PLANS]
    if not eligible:
        return None

    active = [
        subscription
        for subscription in eligible
        if _stripe_get(subscription, "status") in ACTIVE_BILLING_STATUSES
    ]
    candidates = active or eligible
    return max(
        candidates,
        key=lambda item: (
            int(_stripe_get(item, "created", 0) or 0),
            _stripe_id(item) or "",
        ),
    )


def _authoritative_subscription_for_event(user: User, candidate: Any | None) -> Any | None:
    candidate_id = _stripe_id(candidate)
    current_id = user.billing_subscription_id or ""
    if candidate is not None and (not current_id or current_id == candidate_id):
        return candidate
    return _latest_subscription_for_user(user, candidate_subscription=candidate)


@router.post("/checkout", response_model=BillingUrlResponse, dependencies=[Depends(require_api_key)])
def create_checkout_session(
    payload: CheckoutRequest,
    current_user: User = Depends(get_current_user),
    request: Request = None,
) -> BillingUrlResponse:
    site_url = _site_url(request)
    plan = payload.plan.strip().lower()
    if plan not in PAID_PLANS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Plano inválido.")
    if is_owner_email(current_user.email):
        return BillingUrlResponse(url=f"{site_url}/perfil?assinatura=owner")

    with SessionLocal() as db:
        user = lock_user_for_billing_mutation(db, current_user.id)
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário não encontrado.")

        if has_recoverable_provider_subscription(
            db,
            user_id=user.id,
            provider="google_play",
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Existe uma assinatura Google Play ativa ou recuperavel. "
                    "Gerencie-a no Google Play antes de assinar pelo site."
                ),
            )

        if not _stripe_ready_for_plan(plan):
            billing_request = _create_manual_pix_request(db, user, plan)
            return BillingUrlResponse(
                url=f"{site_url}/assinatura/pix?ref={billing_request.reference_code}"
            )

        _configure_stripe()

        completed_checkout_found, _ = _refresh_pending_checkout_intents(db, user)
        customer_id = _ensure_customer(db, user)
        _ensure_no_open_checkout_session(customer_id)

        if completed_checkout_found:
            try:
                confirmed_subscription = _latest_subscription_for_user(user)
            except stripe.error.StripeError as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="O pagamento anterior ainda esta sendo confirmado.",
                ) from exc
            if confirmed_subscription is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="O pagamento anterior ainda esta sendo confirmado.",
                )
            _apply_subscription(db, user, confirmed_subscription)
            if user.billing_status not in ACTIVE_BILLING_STATUSES:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="O pagamento anterior ainda esta sendo confirmado.",
                )

        if user.billing_subscription_id and user.billing_status in ACTIVE_BILLING_STATUSES:
            db.commit()
            return BillingUrlResponse(url=_portal_url(customer_id, request))

        price_id = _price_id_for_plan(plan)
        session_args: dict[str, Any] = {
            "mode": "subscription",
            "customer": customer_id,
            "client_reference_id": str(user.id),
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": f"{site_url}/perfil?assinatura=sucesso",
            "cancel_url": f"{site_url}/planos?assinatura=cancelada",
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
            checkout = stripe.checkout.Session.create(
                **session_args,
                idempotency_key=_checkout_idempotency_key(
                    user_id=user.id,
                    plan=plan,
                ),
            )
        except stripe.error.StripeError as exc:
            # Keep the provider customer link, but do not create a billing intent
            # because Stripe did not return a checkout session.
            db.commit()
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

        checkout_id = _stripe_id(checkout)
        checkout_url = _stripe_get(checkout, "url")
        if not checkout_id or not checkout_url:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Stripe retornou uma sessao de checkout invalida.",
            )
        now = datetime.datetime.utcnow()
        provider_expiry = _timestamp_to_datetime(_stripe_get(checkout, "expires_at"))
        intent_expiry = min(
            provider_expiry or (now + datetime.timedelta(hours=24)),
            now + datetime.timedelta(hours=24),
        )
        if intent_expiry <= now:
            intent_expiry = now + datetime.timedelta(minutes=30)
        upsert_subscription(
            db,
            user=user,
            provider="stripe",
            package_name="",
            provider_status="checkout_pending",
            entitlement_state="pending",
            items=[
                SubscriptionItemInput(
                    item_key=f"stripe-checkout:{plan}",
                    product_id=f"stripe:{plan}",
                    plan=plan,
                    expiry_time=intent_expiry,
                    entitled=False,
                )
            ],
            external_subscription_id=checkout_id,
            provider_customer_id=customer_id,
            current_period_end=intent_expiry,
            provider_event_at=now,
        )
        db.commit()

    return BillingUrlResponse(url=checkout_url)


@router.post(
    "/sync",
    response_model=BillingSyncResponse,
    dependencies=[Depends(require_api_key)],
)
def sync_billing_subscription(
    response: Response,
    current_user: User = Depends(get_current_user),
) -> BillingSyncResponse:
    if is_owner_email(current_user.email):
        return BillingSyncResponse(synced=True, plan="magisterio", billing_status="owner")

    _configure_stripe()
    with SessionLocal() as db:
        user = lock_user_for_billing_mutation(db, current_user.id)
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário não encontrado.")

        try:
            subscription = _latest_subscription_for_user(user)
        except stripe.error.StripeError as exc:
            logger.exception("stripe_sync_failed user_id=%s", user.id)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Não foi possível confirmar a assinatura agora.",
            ) from exc

        if subscription is not None:
            _apply_subscription(db, user, subscription)
        db.commit()
        db.refresh(user)

        synced = user.billing_status in ACTIVE_BILLING_STATUSES and user.plan in PAID_PLANS
        if not synced:
            response.status_code = status.HTTP_202_ACCEPTED
        return BillingSyncResponse(
            synced=synced,
            plan=user.plan,
            billing_status=user.billing_status,
        )


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
def create_portal_session(
    current_user: User = Depends(get_current_user),
    request: Request = None,
) -> BillingUrlResponse:
    if is_owner_email(current_user.email):
        return BillingUrlResponse(url=f"{_site_url(request)}/perfil?assinatura=owner")
    _configure_stripe()

    with SessionLocal() as db:
        user = db.get(User, current_user.id)
        if not user or not user.billing_customer_id:
            raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhuma assinatura encontrada para gerenciar.",
            )
        try:
            return BillingUrlResponse(url=_portal_url(user.billing_customer_id, request))
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


@router.post(
    "/admin/coupons",
    response_model=AdminCouponResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
)
def create_admin_coupon(
    payload: AdminCouponCreateRequest,
    current_user: User = Depends(get_current_user),
) -> AdminCouponResponse:
    _require_owner_admin(current_user)
    _configure_stripe()

    code = payload.code.strip().upper()
    try:
        existing = stripe.PromotionCode.list(code=code, active=True, limit=1)
    except stripe.error.StripeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Nao foi possivel consultar os cupons na Stripe.",
        ) from exc
    if _stripe_get(existing, "data"):
        raise HTTPException(status_code=409, detail="Ja existe um cupom ativo com esse codigo.")

    coupon = None
    try:
        coupon = stripe.Coupon.create(
            duration=payload.duration,
            percent_off=payload.percent_off,
            name=(payload.name or code).strip(),
            metadata={"created_by": "vera_fidei_admin", "code": code},
        )
        promotion_args: dict[str, Any] = {
            "promotion": {"type": "coupon", "coupon": _stripe_get(coupon, "id")},
            "code": code,
            "metadata": {"created_by": "vera_fidei_admin"},
        }
        if payload.max_redemptions is not None:
            promotion_args["max_redemptions"] = payload.max_redemptions
        promotion = stripe.PromotionCode.create(**promotion_args)
        return _coupon_payload_from_promotion_code(promotion)
    except stripe.error.StripeError as exc:
        coupon_id = _stripe_get(coupon, "id")
        if coupon_id:
            try:
                stripe.Coupon.delete(coupon_id)
            except stripe.error.StripeError:
                pass
        message = getattr(exc, "user_message", None) or "A Stripe recusou a criacao do cupom."
        raise HTTPException(status_code=400, detail=message) from exc


CHECKOUT_WEBHOOK_EVENTS = {
    "checkout.session.completed",
    "checkout.session.async_payment_succeeded",
    "checkout.session.async_payment_failed",
}
SUBSCRIPTION_WEBHOOK_EVENTS = {
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
}
INVOICE_WEBHOOK_EVENTS = {
    "invoice.paid",
    "invoice.payment_succeeded",
    "invoice.payment_failed",
}


def _process_stripe_event(db, event_type: str, data: Any) -> bool:
    if event_type in CHECKOUT_WEBHOOK_EVENTS:
        metadata = _stripe_get(data, "metadata") or {}
        subscription_id = _stripe_id(_stripe_get(data, "subscription"))
        customer_id = _stripe_id(_stripe_get(data, "customer"))
        user_id = _stripe_get(metadata, "user_id") or _stripe_get(data, "client_reference_id")
        user = _find_user(
            db,
            user_id=str(user_id) if user_id is not None else None,
            customer_id=customer_id,
            subscription_id=subscription_id,
            email=_event_email(data),
        )
        if not user:
            return False
        user = lock_user_for_billing_mutation(db, user.id)
        if not user or not user.is_active:
            return False
        _close_checkout_intent_for_event(
            db,
            user=user,
            checkout_id=_stripe_id(data),
            event_type=event_type,
        )
        if customer_id and not user.billing_customer_id:
            user.billing_provider = "stripe"
            user.billing_customer_id = customer_id

        candidate = stripe.Subscription.retrieve(subscription_id) if subscription_id else None
        subscription = _authoritative_subscription_for_event(user, candidate)
        if subscription is None:
            return False
        live_metadata = _stripe_get(candidate, "metadata") or {}
        fallback_plan = None
        if _stripe_id(subscription) == subscription_id:
            fallback_plan = _stripe_get(live_metadata, "plan") or _stripe_get(metadata, "plan")
        _apply_subscription(db, user, subscription, fallback_plan=fallback_plan)
        return True

    if event_type in SUBSCRIPTION_WEBHOOK_EVENTS:
        subscription_id = _stripe_id(data)
        event_metadata = _stripe_get(data, "metadata") or {}
        candidate = data
        if subscription_id:
            try:
                candidate = stripe.Subscription.retrieve(subscription_id)
            except stripe.error.InvalidRequestError:
                if event_type != "customer.subscription.deleted":
                    raise

        live_metadata = _stripe_get(candidate, "metadata") or {}
        user_id = _stripe_get(live_metadata, "user_id") or _stripe_get(event_metadata, "user_id")
        customer_id = _stripe_id(_stripe_get(candidate, "customer")) or _stripe_id(
            _stripe_get(data, "customer")
        )
        user = _find_user(
            db,
            user_id=str(user_id) if user_id is not None else None,
            customer_id=customer_id,
            subscription_id=subscription_id,
        )
        if not user:
            return False
        user = lock_user_for_billing_mutation(db, user.id)
        if not user or not user.is_active:
            return False
        if customer_id and not user.billing_customer_id:
            user.billing_provider = "stripe"
            user.billing_customer_id = customer_id

        subscription = _authoritative_subscription_for_event(user, candidate)
        if subscription is None:
            return False
        fallback_plan = None
        if _stripe_id(subscription) == subscription_id:
            fallback_plan = _stripe_get(live_metadata, "plan") or _stripe_get(event_metadata, "plan")
        _apply_subscription(db, user, subscription, fallback_plan=fallback_plan)
        return True

    if event_type in INVOICE_WEBHOOK_EVENTS:
        subscription_id = _invoice_subscription_id(data)
        customer_id = _stripe_id(_stripe_get(data, "customer"))
        user = _find_user(
            db,
            user_id=None,
            customer_id=customer_id,
            subscription_id=subscription_id,
            email=_event_email(data),
        )
        if not user:
            return False
        user = lock_user_for_billing_mutation(db, user.id)
        if not user or not user.is_active:
            return False
        if customer_id and not user.billing_customer_id:
            user.billing_provider = "stripe"
            user.billing_customer_id = customer_id

        candidate = (
            stripe.Subscription.retrieve(subscription_id)
            if subscription_id
            else None
        )
        subscription = _authoritative_subscription_for_event(user, candidate)
        if subscription is None:
            return False
        _apply_subscription(db, user, subscription)
        return True

    return True


def _process_stripe_webhook_payload(
    payload: bytes,
    stripe_signature: str,
) -> dict[str, bool]:
    """Verify and apply a Stripe event from a worker thread."""
    _configure_stripe()
    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=stripe_signature,
            secret=settings.stripe_webhook_secret,
        )
    except (ValueError, stripe.error.SignatureVerificationError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Webhook inválido.") from exc

    event_type = str(_stripe_get(event, "type") or "")
    event_id = _stripe_id(event) or "unknown"
    data = _stripe_get(_stripe_get(event, "data") or {}, "object") or {}

    try:
        with SessionLocal() as db:
            processed = _process_stripe_event(db, event_type, data)
            if not processed:
                logger.warning(
                    "stripe_webhook_acknowledged_without_local_match event_type=%s event_suffix=%s",
                    event_type,
                    event_id[-8:],
                )
            db.commit()
    except Exception as exc:
        logger.exception(
            "stripe_webhook_processing_failed event_type=%s event_suffix=%s",
            event_type,
            event_id[-8:],
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Falha temporária ao aplicar o evento de assinatura.",
        ) from exc

    return {"received": True}


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
    payload = await request.body()
    return await run_in_threadpool(
        _process_stripe_webhook_payload,
        payload,
        stripe_signature,
    )
