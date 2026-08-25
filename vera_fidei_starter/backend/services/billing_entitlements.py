from __future__ import annotations

import datetime
from dataclasses import dataclass

from sqlalchemy.orm import Session

from core.plans import DEFAULT_PLAN, ensure_owner_access, is_owner_email, plan_rank
from models.database import BillingRateLimit, BillingSubscription, BillingSubscriptionItem, User


# Keep the paid-plan definition local to the billing boundary. Importing it
# from the Stripe route would create a circular dependency.
PAID_PLAN_NAMES = frozenset({"catequista", "apologeta", "patristico", "magisterio"})
ACCESS_STATES = frozenset({"entitled", "grace", "canceled_valid", "legacy_active"})
RECOVERABLE_STATES = frozenset(
    {"entitled", "grace", "canceled_valid", "legacy_active", "paused", "hold", "pending"}
)
PROVIDER_PRIORITY = {"legacy_manual": 0, "manual_pix": 1, "stripe": 2, "google_play": 3}


class BillingOwnershipConflict(RuntimeError):
    pass


class BillingRateLimitExceeded(RuntimeError):
    def __init__(self, retry_after_seconds: int):
        super().__init__("Billing synchronization rate limit exceeded.")
        self.retry_after_seconds = max(1, int(retry_after_seconds))


@dataclass(frozen=True)
class SubscriptionItemInput:
    item_key: str
    product_id: str
    plan: str
    base_plan_id: str | None = None
    offer_id: str | None = None
    expiry_time: datetime.datetime | None = None
    auto_renew_enabled: bool = False
    entitled: bool = False


@dataclass(frozen=True)
class EffectiveBillingStatus:
    plan: str
    billing_status: str | None
    active_product_id: str | None
    provider: str | None
    current_period_end: datetime.datetime | None


def utcnow() -> datetime.datetime:
    return datetime.datetime.utcnow()


def stripe_entitlement_state(
    status_value: str | None,
    current_period_end: datetime.datetime | None,
) -> str:
    status = (status_value or "").strip().lower()
    if status in {"active", "trialing"}:
        return "entitled"
    if status == "past_due":
        return "grace"
    if status == "canceled" and current_period_end and current_period_end > utcnow():
        return "canceled_valid"
    if status in {"incomplete", "pending_payment"}:
        return "pending"
    if status == "paused":
        return "paused"
    if status == "unpaid":
        return "hold"
    return "inactive"


def upsert_subscription(
    db: Session,
    *,
    user: User,
    provider: str,
    package_name: str,
    provider_status: str,
    entitlement_state: str,
    items: list[SubscriptionItemInput],
    external_subscription_id: str | None = None,
    provider_customer_id: str | None = None,
    purchase_token_hash: str | None = None,
    purchase_token_ciphertext: str | None = None,
    linked_purchase_token_hash: str | None = None,
    acknowledgement_state: str | None = None,
    current_period_end: datetime.datetime | None = None,
    auto_renew_enabled: bool = False,
    cancel_at_period_end: bool = False,
    test_purchase: bool = False,
    provider_event_at: datetime.datetime | None = None,
    last_order_id: str | None = None,
    etag: str | None = None,
) -> BillingSubscription:
    subscription: BillingSubscription | None = None
    if purchase_token_hash:
        subscription = (
            db.query(BillingSubscription)
            .filter(
                BillingSubscription.provider == provider,
                BillingSubscription.package_name == package_name,
                BillingSubscription.purchase_token_hash == purchase_token_hash,
            )
            .first()
        )
    if subscription is None and external_subscription_id:
        subscription = (
            db.query(BillingSubscription)
            .filter(
                BillingSubscription.provider == provider,
                BillingSubscription.external_subscription_id == external_subscription_id,
            )
            .first()
        )

    if subscription is not None and subscription.user_id != user.id:
        raise BillingOwnershipConflict("A assinatura ja pertence a outra conta.")

    if subscription is None:
        subscription = BillingSubscription(
            user_id=user.id,
            provider=provider,
            package_name=package_name,
        )
        db.add(subscription)

    subscription.provider_customer_id = provider_customer_id
    subscription.external_subscription_id = external_subscription_id
    subscription.purchase_token_hash = purchase_token_hash
    if purchase_token_ciphertext is not None:
        subscription.purchase_token_ciphertext = purchase_token_ciphertext
    subscription.linked_purchase_token_hash = linked_purchase_token_hash
    subscription.provider_status = provider_status
    subscription.entitlement_state = entitlement_state
    subscription.acknowledgement_state = acknowledgement_state
    subscription.current_period_end = current_period_end
    subscription.auto_renew_enabled = auto_renew_enabled
    subscription.cancel_at_period_end = cancel_at_period_end
    subscription.test_purchase = test_purchase
    subscription.provider_event_at = provider_event_at
    subscription.last_verified_at = utcnow()
    subscription.last_order_id = last_order_id
    subscription.etag = etag
    subscription.updated_at = utcnow()
    db.flush()

    db.query(BillingSubscriptionItem).filter(
        BillingSubscriptionItem.billing_subscription_id == subscription.id
    ).delete(synchronize_session=False)
    for item in items:
        if item.plan not in PAID_PLAN_NAMES:
            continue
        db.add(
            BillingSubscriptionItem(
                billing_subscription_id=subscription.id,
                item_key=item.item_key,
                product_id=item.product_id,
                base_plan_id=item.base_plan_id,
                offer_id=item.offer_id,
                plan=item.plan,
                expiry_time=item.expiry_time,
                auto_renew_enabled=item.auto_renew_enabled,
                entitled=item.entitled,
            )
        )
    db.flush()
    return subscription


def record_stripe_projection(
    db: Session,
    *,
    user: User,
    subscription_id: str | None,
    customer_id: str | None,
    status_value: str | None,
    plan: str | None,
    current_period_end: datetime.datetime | None,
    cancel_at_period_end: bool,
) -> BillingSubscription | None:
    if not subscription_id:
        return None
    state = stripe_entitlement_state(status_value, current_period_end)
    item_inputs: list[SubscriptionItemInput] = []
    if plan in PAID_PLAN_NAMES:
        item_inputs.append(
            SubscriptionItemInput(
                item_key=f"stripe:{plan}",
                product_id=f"stripe:{plan}",
                plan=plan,
                expiry_time=current_period_end,
                auto_renew_enabled=not cancel_at_period_end,
                entitled=state in ACCESS_STATES,
            )
        )
    return upsert_subscription(
        db,
        user=user,
        provider="stripe",
        package_name="",
        provider_status=(status_value or "unknown"),
        entitlement_state=state,
        items=item_inputs,
        external_subscription_id=subscription_id,
        provider_customer_id=customer_id,
        current_period_end=current_period_end,
        auto_renew_enabled=not cancel_at_period_end,
        cancel_at_period_end=cancel_at_period_end,
    )


def _eligible_items(db: Session, user_id: int) -> list[tuple[BillingSubscription, BillingSubscriptionItem]]:
    rows = (
        db.query(BillingSubscription, BillingSubscriptionItem)
        .join(
            BillingSubscriptionItem,
            BillingSubscriptionItem.billing_subscription_id == BillingSubscription.id,
        )
        .filter(BillingSubscription.user_id == user_id)
        .all()
    )
    now = utcnow()
    eligible: list[tuple[BillingSubscription, BillingSubscriptionItem]] = []
    for subscription, item in rows:
        if subscription.entitlement_state not in ACCESS_STATES or not item.entitled:
            continue
        effective_expiry = item.expiry_time or subscription.current_period_end
        if effective_expiry is not None and effective_expiry <= now:
            continue
        if item.plan not in PAID_PLAN_NAMES:
            continue
        eligible.append((subscription, item))
    return eligible


def effective_billing_status(db: Session, user: User) -> EffectiveBillingStatus:
    if is_owner_email(user.email):
        ensure_owner_access(user)
        return EffectiveBillingStatus(
            plan="magisterio",
            billing_status="owner",
            active_product_id=None,
            provider=None,
            current_period_end=None,
        )

    eligible = _eligible_items(db, user.id)
    if eligible:
        subscription, item = max(
            eligible,
            key=lambda row: (
                plan_rank(row[1].plan),
                PROVIDER_PRIORITY.get(row[0].provider, -1),
                row[0].id or 0,
            ),
        )
        return EffectiveBillingStatus(
            plan=item.plan,
            billing_status=subscription.provider_status,
            active_product_id=item.product_id if subscription.provider == "google_play" else None,
            provider=subscription.provider,
            current_period_end=item.expiry_time or subscription.current_period_end,
        )

    fallback = (
        db.query(BillingSubscription)
        .filter(BillingSubscription.user_id == user.id)
        .order_by(BillingSubscription.updated_at.desc(), BillingSubscription.id.desc())
        .first()
    )
    fallback_status = fallback.provider_status if fallback else None
    fallback_period_end = fallback.current_period_end if fallback else None
    if fallback is not None and fallback_period_end is None:
        latest_item = (
            db.query(BillingSubscriptionItem)
            .filter(
                BillingSubscriptionItem.billing_subscription_id == fallback.id,
                BillingSubscriptionItem.expiry_time.is_not(None),
            )
            .order_by(
                BillingSubscriptionItem.expiry_time.desc(),
                BillingSubscriptionItem.id.desc(),
            )
            .first()
        )
        if latest_item is not None:
            fallback_period_end = latest_item.expiry_time
    if fallback is not None and fallback_period_end is not None and fallback_period_end <= utcnow():
        if fallback.entitlement_state == "pending":
            fallback_status = (
                "checkout_expired"
                if fallback.provider == "stripe" and fallback.provider_status == "checkout_pending"
                else "expired"
            )
        elif (
            fallback.entitlement_state in ACCESS_STATES
            and fallback.provider_status != "canceled"
        ):
            fallback_status = "expired"
    return EffectiveBillingStatus(
        plan=DEFAULT_PLAN,
        billing_status=fallback_status,
        active_product_id=None,
        provider=fallback.provider if fallback else None,
        current_period_end=fallback_period_end,
    )


def recompute_user_plan(db: Session, user: User) -> EffectiveBillingStatus:
    status = effective_billing_status(db, user)
    if user.plan != status.plan:
        user.plan = status.plan
        db.flush()
    return status


def refresh_managed_user_plan(db: Session, user: User) -> EffectiveBillingStatus | None:
    """Refresh expiry projection when this account already has a billing ledger."""
    has_billing_ledger = (
        db.query(BillingSubscription.id)
        .filter(BillingSubscription.user_id == user.id)
        .first()
        is not None
    )
    if not has_billing_ledger:
        return None
    return recompute_user_plan(db, user)


def lock_user_for_billing_mutation(db: Session, user_id: int) -> User | None:
    """Serialize billing mutations and account deletion on the user row."""
    return (
        db.query(User)
        .filter(User.id == user_id)
        .with_for_update()
        .one_or_none()
    )


def has_recoverable_provider_subscription(
    db: Session,
    *,
    user_id: int,
    provider: str,
) -> bool:
    """Return whether another checkout could create a duplicate live charge."""
    rows = (
        db.query(BillingSubscription)
        .filter(
            BillingSubscription.user_id == user_id,
            BillingSubscription.provider == provider,
            BillingSubscription.entitlement_state.in_(RECOVERABLE_STATES),
        )
        .all()
    )
    now = utcnow()
    for row in rows:
        if (
            row.entitlement_state == "pending"
            and row.current_period_end is not None
            and row.current_period_end <= now
        ):
            continue
        if (
            row.entitlement_state in ACCESS_STATES
            and row.current_period_end is not None
            and row.current_period_end <= now
        ):
            continue
        return True
    return False


def consume_billing_rate_limit(
    db: Session,
    *,
    user_id: int,
    scope: str,
    limit: int,
    window_seconds: int,
    cost: int = 1,
    now: datetime.datetime | None = None,
) -> None:
    """Consume a DB-backed rate-limit slot while the caller holds the user lock."""
    if limit < 1 or window_seconds < 1 or cost < 1:
        raise ValueError("Invalid billing rate-limit configuration.")
    if cost > limit:
        raise BillingRateLimitExceeded(window_seconds)
    current = now or utcnow()
    row = (
        db.query(BillingRateLimit)
        .filter(BillingRateLimit.user_id == user_id, BillingRateLimit.scope == scope)
        .with_for_update()
        .one_or_none()
    )
    if row is None:
        db.add(
            BillingRateLimit(
                user_id=user_id,
                scope=scope,
                window_started_at=current,
                attempts=cost,
                updated_at=current,
            )
        )
        db.flush()
        return

    elapsed = max(0.0, (current - row.window_started_at).total_seconds())
    if elapsed >= window_seconds:
        row.window_started_at = current
        row.attempts = cost
        row.updated_at = current
        db.flush()
        return
    if row.attempts + cost > limit:
        raise BillingRateLimitExceeded(int(window_seconds - elapsed) + 1)
    row.attempts += cost
    row.updated_at = current
    db.flush()


def google_subscription_blocks_deletion(subscription: BillingSubscription) -> bool:
    if subscription.provider != "google_play":
        return False
    if subscription.entitlement_state in {"paused", "hold", "pending"}:
        return True
    if subscription.entitlement_state in ACCESS_STATES:
        if subscription.current_period_end is None:
            return True
        return subscription.current_period_end > utcnow()
    return False


def sanitized_subscriptions_for_export(db: Session, user_id: int) -> list[dict[str, object]]:
    subscriptions = (
        db.query(BillingSubscription)
        .filter(BillingSubscription.user_id == user_id)
        .order_by(BillingSubscription.created_at.asc(), BillingSubscription.id.asc())
        .all()
    )
    result: list[dict[str, object]] = []
    for subscription in subscriptions:
        items = (
            db.query(BillingSubscriptionItem)
            .filter(BillingSubscriptionItem.billing_subscription_id == subscription.id)
            .order_by(BillingSubscriptionItem.id.asc())
            .all()
        )
        result.append(
            {
                "provider": subscription.provider,
                "status": subscription.provider_status,
                "entitlement_state": subscription.entitlement_state,
                "current_period_end": subscription.current_period_end.isoformat()
                if subscription.current_period_end
                else None,
                "auto_renew_enabled": bool(subscription.auto_renew_enabled),
                "cancel_at_period_end": bool(subscription.cancel_at_period_end),
                "test_purchase": bool(subscription.test_purchase),
                "last_verified_at": subscription.last_verified_at.isoformat()
                if subscription.last_verified_at
                else None,
                "items": [
                    {
                        "product_id": item.product_id,
                        "base_plan_id": item.base_plan_id,
                        "offer_id": item.offer_id,
                        "plan": item.plan,
                        "expiry_time": item.expiry_time.isoformat() if item.expiry_time else None,
                        "auto_renew_enabled": bool(item.auto_renew_enabled),
                        "entitled": bool(item.entitled),
                    }
                    for item in items
                ],
            }
        )
    return result
