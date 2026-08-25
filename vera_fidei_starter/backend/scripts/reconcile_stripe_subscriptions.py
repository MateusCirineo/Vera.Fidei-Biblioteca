from __future__ import annotations

import argparse
import json
import sys

import stripe
from sqlalchemy import or_

from api.routes.billing import _apply_subscription, _latest_subscription_for_user
from core.config import settings
from core.plans import is_owner_email
from models.database import SessionLocal, User
from services.billing_entitlements import lock_user_for_billing_mutation


def _state(user: User) -> tuple[object, ...]:
    return (
        user.plan,
        user.billing_provider,
        user.billing_customer_id,
        user.billing_subscription_id,
        user.billing_status,
        user.billing_current_period_end,
        user.billing_cancel_at_period_end,
    )


def run(*, apply: bool) -> dict[str, object]:
    if settings.billing_provider != "stripe" or not settings.stripe_secret_key:
        raise RuntimeError("Stripe billing is not configured")
    stripe.api_key = settings.stripe_secret_key

    summary: dict[str, object] = {
        "mode": "apply" if apply else "dry-run",
        "checked": 0,
        "changed": 0,
        "unchanged": 0,
        "without_subscription": 0,
        "errors": [],
    }

    with SessionLocal() as db:
        users = (
            db.query(User)
            .filter(
                User.is_active.is_(True),
                or_(
                    User.billing_provider == "stripe",
                    User.billing_customer_id.is_not(None),
                ),
            )
            .order_by(User.id.asc())
            .all()
        )

        for user in users:
            if is_owner_email(user.email):
                continue
            summary["checked"] = int(summary["checked"]) + 1
            try:
                user = lock_user_for_billing_mutation(db, user.id)
                if user is None or not user.is_active:
                    db.rollback()
                    continue
                before = _state(user)
                subscription = _latest_subscription_for_user(user)
                if subscription is None:
                    summary["without_subscription"] = int(summary["without_subscription"]) + 1
                    db.rollback()
                    continue

                _apply_subscription(db, user, subscription)
                db.flush()
                if _state(user) == before:
                    summary["unchanged"] = int(summary["unchanged"]) + 1
                else:
                    summary["changed"] = int(summary["changed"]) + 1

                if apply:
                    db.commit()
                else:
                    db.rollback()
            except Exception as exc:
                db.rollback()
                errors = summary["errors"]
                assert isinstance(errors, list)
                errors.append({"user_id": user.id, "error_type": type(exc).__name__})

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reconcile Vera.Fidei subscription state from Stripe without creating charges."
    )
    parser.add_argument("--apply", action="store_true", help="Persist confirmed Stripe state")
    args = parser.parse_args()

    summary = run(apply=args.apply)
    print(json.dumps(summary, ensure_ascii=False, default=str))
    return 1 if summary["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
