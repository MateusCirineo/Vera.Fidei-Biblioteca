from __future__ import annotations

import argparse
import json
import sys

from core.config import settings
from scripts import reconcile_google_play_subscriptions, reconcile_stripe_subscriptions


def run(*, apply: bool) -> dict[str, object]:
    stripe_configured = bool(
        settings.billing_provider == "stripe" and settings.stripe_secret_key.strip()
    )
    if stripe_configured:
        stripe_result: dict[str, object] = reconcile_stripe_subscriptions.run(apply=apply)
    else:
        stripe_result = {"enabled": False, "skipped": True, "errors": []}
    google_result = reconcile_google_play_subscriptions.run(apply=apply)
    return {
        "mode": "apply" if apply else "dry-run",
        "stripe": stripe_result,
        "google_play": google_result,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reconcile Stripe and Google Play billing state."
    )
    parser.add_argument("--apply", action="store_true", help="Persist verified provider state")
    args = parser.parse_args()
    try:
        summary = run(apply=args.apply)
    except Exception as exc:
        print(json.dumps({"error_type": type(exc).__name__}))
        return 1
    print(json.dumps(summary, ensure_ascii=False, default=str))
    providers = (summary["stripe"], summary["google_play"])
    return 1 if any(provider.get("errors") for provider in providers) else 0


if __name__ == "__main__":
    sys.exit(main())
