from __future__ import annotations

import argparse
import datetime
import json
import sys

from sqlalchemy import case, or_
from services.billing_entitlements import (
    BillingOwnershipConflict,
    lock_user_for_billing_mutation,
    recompute_user_plan,
)
from services.google_play_billing import (
    GooglePlayAPIError,
    GooglePlayConfigurationError,
    decrypt_purchase_token,
    get_google_play_client,
    parse_verified_subscription,
    persist_verified_purchase,
    product_catalog_by_id,
    validate_google_play_configuration,
)
from core.config import settings
from models.database import BillingSubscription, BillingSubscriptionItem, SessionLocal, User


RECONCILABLE_STATES = {
    "entitled",
    "grace",
    "canceled_valid",
    "paused",
    "hold",
    "pending",
}


def _state(subscription: BillingSubscription, user: User) -> tuple[object, ...]:
    return (
        user.plan,
        subscription.provider_status,
        subscription.entitlement_state,
        subscription.acknowledgement_state,
        subscription.current_period_end,
        subscription.auto_renew_enabled,
        subscription.cancel_at_period_end,
    )


def run(*, apply: bool) -> dict[str, object]:
    summary: dict[str, object] = {
        "mode": "apply" if apply else "dry-run",
        "enabled": bool(settings.google_play_enabled),
        "checked": 0,
        "changed": 0,
        "unchanged": 0,
        "acknowledged": 0,
        "errors": [],
    }
    if not settings.google_play_enabled:
        return summary

    validate_google_play_configuration()
    client = get_google_play_client()
    catalog = product_catalog_by_id(strict=True)

    with SessionLocal() as db:
        stale_before = datetime.datetime.utcnow() - datetime.timedelta(
            hours=int(settings.google_play_reconcile_stale_hours)
        )
        subscriptions = (
            db.query(BillingSubscription)
            .filter(
                BillingSubscription.provider == "google_play",
                BillingSubscription.purchase_token_ciphertext.is_not(None),
                BillingSubscription.entitlement_state.in_(RECONCILABLE_STATES),
                or_(
                    BillingSubscription.acknowledgement_state
                    != "ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED",
                    BillingSubscription.acknowledgement_state.is_(None),
                    BillingSubscription.last_verified_at.is_(None),
                    BillingSubscription.last_verified_at <= stale_before,
                ),
            )
            .order_by(
                case(
                    (
                        BillingSubscription.acknowledgement_state
                        != "ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED",
                        0,
                    ),
                    else_=1,
                ),
                BillingSubscription.last_verified_at.asc(),
                BillingSubscription.id.asc(),
            )
            .limit(int(settings.google_play_reconcile_batch_size))
            .all()
        )
        for subscription in subscriptions:
            summary["checked"] = int(summary["checked"]) + 1
            local_id = subscription.id
            user = db.get(User, subscription.user_id)
            if user is None:
                errors = summary["errors"]
                assert isinstance(errors, list)
                errors.append({"subscription_id": local_id, "error_type": "MissingUser"})
                continue
            before = _state(subscription, user)
            try:
                purchase_token = decrypt_purchase_token(subscription.purchase_token_ciphertext or "")
                verified = parse_verified_subscription(client.get_subscription(purchase_token), catalog)
                if apply:
                    user = lock_user_for_billing_mutation(db, user.id)
                    if user is None or not user.is_active:
                        raise BillingOwnershipConflict("Conta indisponivel.")
                    stored = persist_verified_purchase(
                        db,
                        user=user,
                        purchase_token=purchase_token,
                        verified=verified,
                    )
                    recompute_user_plan(db, user)
                    db.commit()
                    if verified.entitlement_granted and verified.requires_acknowledgement:
                        client.acknowledge_subscription(purchase_token, verified.items[0].product_id)
                        stored = db.get(BillingSubscription, stored.id)
                        if stored is not None:
                            stored.acknowledgement_state = "ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED"
                            db.commit()
                        summary["acknowledged"] = int(summary["acknowledged"]) + 1
                    subscription = db.get(BillingSubscription, local_id)
                    user = db.get(User, user.id)
                    after = _state(subscription, user) if subscription and user else before
                else:
                    after = (
                        verified.items[0].plan if verified.entitlement_granted else "fiel",
                        verified.provider_status,
                        verified.entitlement_state,
                        verified.acknowledgement_state,
                        verified.current_period_end,
                        verified.auto_renew_enabled,
                        verified.entitlement_state == "canceled_valid",
                    )
                    db.rollback()
                key = "changed" if after != before else "unchanged"
                summary[key] = int(summary[key]) + 1
            except GooglePlayAPIError as exc:
                terminal_expired = bool(
                    exc.status_code in {404, 410}
                    and subscription.current_period_end is not None
                    and subscription.current_period_end <= datetime.datetime.utcnow()
                )
                if terminal_expired:
                    if apply:
                        user = lock_user_for_billing_mutation(db, user.id)
                        if user is None or not user.is_active:
                            db.rollback()
                            errors = summary["errors"]
                            assert isinstance(errors, list)
                            errors.append(
                                {
                                    "subscription_id": local_id,
                                    "error_type": "BillingOwnershipConflict",
                                }
                            )
                            continue
                        subscription.provider_status = "SUBSCRIPTION_STATE_EXPIRED"
                        subscription.entitlement_state = "inactive"
                        subscription.auto_renew_enabled = False
                        subscription.cancel_at_period_end = False
                        subscription.last_verified_at = datetime.datetime.utcnow()
                        db.query(BillingSubscriptionItem).filter(
                            BillingSubscriptionItem.billing_subscription_id == subscription.id
                        ).update(
                            {BillingSubscriptionItem.entitled: False},
                            synchronize_session=False,
                        )
                        recompute_user_plan(db, user)
                        db.commit()
                    else:
                        db.rollback()
                    summary["changed"] = int(summary["changed"]) + 1
                    continue
                db.rollback()
                errors = summary["errors"]
                assert isinstance(errors, list)
                errors.append({"subscription_id": local_id, "error_type": type(exc).__name__})
            except (BillingOwnershipConflict, GooglePlayConfigurationError) as exc:
                db.rollback()
                errors = summary["errors"]
                assert isinstance(errors, list)
                errors.append({"subscription_id": local_id, "error_type": type(exc).__name__})
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reconcile Google Play subscriptions without exposing purchase tokens."
    )
    parser.add_argument("--apply", action="store_true", help="Persist verified provider state")
    args = parser.parse_args()
    try:
        summary = run(apply=args.apply)
    except GooglePlayConfigurationError as exc:
        print(json.dumps({"error_type": type(exc).__name__}))
        return 1
    print(json.dumps(summary, ensure_ascii=False, default=str))
    return 1 if summary["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
