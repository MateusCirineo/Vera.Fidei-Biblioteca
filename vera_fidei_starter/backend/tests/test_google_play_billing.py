from __future__ import annotations

import base64
import datetime
import hashlib
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from cryptography.fernet import Fernet
from fastapi import HTTPException, Response
from fastapi.exceptions import RequestValidationError
from starlette.requests import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.routes import auth, billing as stripe_routes, google_play_billing as routes
from core import api_key_auth, deps
from core.config import settings
from models.database import (
    Base,
    ApiKey,
    BillingEvent,
    BillingRateLimit,
    BillingSubscription,
    BillingSubscriptionItem,
    User,
)
from models import database as database_models
from scripts import reconcile_google_play_subscriptions as reconciler
from scripts import reconcile_billing_subscriptions as unified_reconciler
from services import google_play_billing as google_play_service
from services.billing_entitlements import (
    SubscriptionItemInput,
    effective_billing_status,
    has_recoverable_provider_subscription,
    lock_user_for_billing_mutation,
    record_stripe_projection,
    recompute_user_plan,
    upsert_subscription,
)
from services.google_play_billing import (
    GooglePlayAPIError,
    GooglePlayConfigurationError,
    decrypt_purchase_token,
    entitlement_state_for_google,
    load_product_catalog,
    obfuscated_account_id,
    purchase_token_fingerprint,
    validate_google_play_configuration,
)


PRODUCTS = [
    {"product_id": "vf.sub.catequista", "plan": "catequista", "base_plan_id": "monthly"},
    {"product_id": "vf.sub.apologeta", "plan": "apologeta", "base_plan_id": "monthly"},
    {"product_id": "vf.sub.patristico", "plan": "patristico", "base_plan_id": "monthly"},
    {"product_id": "vf.sub.magisterio", "plan": "magisterio", "base_plan_id": "monthly"},
]


class BodyRequest:
    def __init__(self, body: bytes):
        self._body = body

    async def body(self) -> bytes:
        return self._body


class FakeGooglePlayClient:
    def __init__(self, payloads: dict[str, dict]):
        self.payloads = payloads
        self.get_calls: list[str] = []
        self.ack_calls: list[tuple[str, str]] = []

    def get_subscription(self, token: str) -> dict:
        self.get_calls.append(token)
        value = self.payloads[token]
        if isinstance(value, Exception):
            raise value
        return value

    def acknowledge_subscription(self, token: str, product_id: str) -> None:
        self.ack_calls.append((token, product_id))


class GooglePlayBillingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(
            self.engine,
            tables=[
                User.__table__,
                ApiKey.__table__,
                BillingSubscription.__table__,
                BillingSubscriptionItem.__table__,
                BillingEvent.__table__,
                BillingRateLimit.__table__,
            ],
        )
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.session_factory() as db:
            db.add(
                User(
                    id=41,
                    email="reader@example.com",
                    name="Reader",
                    password_hash="unused",
                    plan="fiel",
                    is_active=True,
                    email_verified=True,
                )
            )
            db.commit()

        self.token_key = Fernet.generate_key().decode("ascii")
        self.setting_patchers = [
            patch.object(settings, "google_play_enabled", True),
            patch.object(settings, "google_play_package_name", "com.verafidei.app"),
            patch.object(settings, "google_play_products_json", json.dumps(PRODUCTS)),
            patch.object(settings, "google_play_token_encryption_key", self.token_key),
            patch.object(settings, "google_play_account_hmac_secret", "h" * 48),
            patch.object(settings, "google_play_require_obfuscated_account_id", True),
            patch.object(settings, "google_play_pubsub_audience", "https://api.example/rtdn"),
            patch.object(
                settings,
                "google_play_pubsub_service_account_email",
                "pubsub@example.iam.gserviceaccount.com",
            ),
            patch.object(
                settings,
                "google_play_pubsub_subscription",
                "projects/project/subscriptions/vera-rtdn",
            ),
            patch.object(settings, "google_play_reconcile_stale_hours", 6),
            patch.object(settings, "google_play_reconcile_batch_size", 200),
            patch.object(settings, "google_play_sync_rate_limit", 20),
            patch.object(settings, "google_play_sync_rate_window_seconds", 60),
        ]
        for patcher in self.setting_patchers:
            patcher.start()
        self.addCleanup(self._cleanup)

    def _cleanup(self) -> None:
        for patcher in reversed(self.setting_patchers):
            patcher.stop()
        self.engine.dispose()

    @property
    def current_user(self):
        return SimpleNamespace(id=41, email="reader@example.com")

    def _payload(
        self,
        *,
        product_id: str = "vf.sub.catequista",
        state: str = "SUBSCRIPTION_STATE_ACTIVE",
        acknowledged: bool = False,
        account_id: str | None = None,
        expiry_delta: datetime.timedelta = datetime.timedelta(days=30),
        linked_token: str | None = None,
    ) -> dict:
        payload = {
            "subscriptionState": state,
            "acknowledgementState": (
                "ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED"
                if acknowledged
                else "ACKNOWLEDGEMENT_STATE_PENDING"
            ),
            "externalAccountIdentifiers": {
                "obfuscatedExternalAccountId": account_id or obfuscated_account_id(41)
            },
            "lineItems": [
                {
                    "productId": product_id,
                    "expiryTime": (
                        datetime.datetime.utcnow() + expiry_delta
                    ).replace(microsecond=0).isoformat() + "Z",
                    "latestSuccessfulOrderId": "GPA.1234-5678-9012-34567",
                    "autoRenewingPlan": {"autoRenewEnabled": True},
                    "offerDetails": {"basePlanId": "monthly"},
                }
            ],
        }
        if linked_token:
            payload["linkedPurchaseToken"] = linked_token
        return payload

    def _sync(
        self,
        token: str,
        client: FakeGooglePlayClient,
        product_id: str | None = None,
        current_user=None,
    ):
        purchase = {"purchase_token": token}
        if product_id:
            purchase["product_id"] = product_id
        with (
            patch.object(routes, "SessionLocal", self.session_factory),
            patch.object(routes, "_require_enabled"),
            patch.object(routes, "get_google_play_client", return_value=client),
        ):
            self.last_http_response = Response()
            return routes.sync_google_play_subscriptions(
                routes.GooglePlayPurchaseBatch(purchases=[purchase]),
                self.last_http_response,
                current_user or self.current_user,
            )

    def _subscription_envelope(
        self,
        *,
        token: str,
        notification_type: int,
        message_id: str,
    ) -> bytes:
        notification = {
            "version": "1.0",
            "packageName": "com.verafidei.app",
            "eventTimeMillis": "1800000000000",
            "subscriptionNotification": {
                "notificationType": notification_type,
                "purchaseToken": token,
                "subscriptionId": "vf.sub.catequista",
            },
        }
        envelope = {
            "subscription": "projects/project/subscriptions/vera-rtdn",
            "message": {
                "messageId": message_id,
                "data": base64.b64encode(json.dumps(notification).encode()).decode(),
            },
        }
        return json.dumps(envelope).encode()

    def test_sync_grants_entitlement_acknowledges_and_never_echoes_token(self) -> None:
        token = "purchase-token-secret-0001"
        client = FakeGooglePlayClient({token: self._payload()})
        response = self._sync(token, client, "vf.sub.catequista")

        self.assertTrue(response.synced)
        self.assertEqual(response.plan, "catequista")
        self.assertEqual(response.active_product_id, "vf.sub.catequista")
        self.assertTrue(response.results[0].accepted)
        self.assertTrue(response.results[0].entitlement_granted)
        self.assertTrue(response.results[0].finish_transaction)
        self.assertNotIn(token, json.dumps(response.model_dump()))
        self.assertEqual(client.ack_calls, [(token, "vf.sub.catequista")])
        self.assertEqual(self.last_http_response.headers["cache-control"], "no-store, max-age=0")
        status_response = Response()
        with patch.object(routes, "SessionLocal", self.session_factory):
            current = routes.billing_status(status_response, self.current_user)
        self.assertEqual(current.plan, "catequista")
        self.assertEqual(status_response.headers["cache-control"], "no-store, max-age=0")

        with self.session_factory() as db:
            subscription = db.query(BillingSubscription).one()
            user = db.get(User, 41)
            self.assertEqual(subscription.purchase_token_hash, purchase_token_fingerprint(token))
            self.assertNotEqual(subscription.purchase_token_ciphertext, token)
            self.assertEqual(decrypt_purchase_token(subscription.purchase_token_ciphertext), token)
            self.assertEqual(subscription.acknowledgement_state, "ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED")
            self.assertEqual(user.plan, "catequista")

    def test_sync_rejects_product_and_account_mismatches(self) -> None:
        token_a = "purchase-token-secret-0002"
        client_a = FakeGooglePlayClient({token_a: self._payload()})
        response_a = self._sync(token_a, client_a, "vf.sub.apologeta")
        self.assertFalse(response_a.synced)
        self.assertEqual(response_a.results[0].state, "product_mismatch")

        token_b = "purchase-token-secret-0003"
        client_b = FakeGooglePlayClient(
            {token_b: self._payload(account_id="vf_account_from_another_user")}
        )
        response_b = self._sync(token_b, client_b)
        self.assertFalse(response_b.synced)
        self.assertEqual(response_b.results[0].state, "ownership_conflict")
        with self.session_factory() as db:
            self.assertEqual(db.query(BillingSubscription).count(), 0)

        token_c = "purchase-token-secret-base-plan"
        wrong_base = self._payload()
        wrong_base["lineItems"][0]["offerDetails"]["basePlanId"] = "annual"
        response_c = self._sync(token_c, FakeGooglePlayClient({token_c: wrong_base}))
        self.assertFalse(response_c.synced)
        self.assertEqual(response_c.results[0].state, "rejected")

        for suffix, expiry in (("missing", None), ("invalid", "not-a-date")):
            token_d = f"purchase-token-secret-expiry-{suffix}"
            invalid_expiry = self._payload()
            if expiry is None:
                invalid_expiry["lineItems"][0].pop("expiryTime")
            else:
                invalid_expiry["lineItems"][0]["expiryTime"] = expiry
            response_d = self._sync(
                token_d,
                FakeGooglePlayClient({token_d: invalid_expiry}),
            )
            self.assertFalse(response_d.synced)
            self.assertEqual(response_d.results[0].state, "rejected")

        no_current_token = "purchase-token-secret-expiry-past"
        no_current = self._payload(expiry_delta=-datetime.timedelta(days=1))
        no_current_response = self._sync(
            no_current_token,
            FakeGooglePlayClient({no_current_token: no_current}),
        )
        self.assertFalse(no_current_response.synced)
        self.assertEqual(no_current_response.results[0].state, "rejected")

    def test_deferred_replacement_grants_only_current_item_and_item_keys_do_not_collide(self) -> None:
        token = "purchase-token-secret-deferred-two-items"
        shared_order_id = "GPA.shared-order-id"
        future = (datetime.datetime.utcnow() + datetime.timedelta(days=10)).replace(
            microsecond=0
        ).isoformat() + "Z"
        payload = self._payload(acknowledged=True)
        payload["lineItems"] = [
            {
                "productId": "vf.sub.catequista",
                "expiryTime": future,
                "latestSuccessfulOrderId": shared_order_id,
                "autoRenewingPlan": {"autoRenewEnabled": False},
                "offerDetails": {"basePlanId": "monthly"},
                "deferredItemReplacement": {"productId": "vf.sub.apologeta"},
            },
            {
                "productId": "vf.sub.apologeta",
                "latestSuccessfulOrderId": shared_order_id,
                "autoRenewingPlan": {"autoRenewEnabled": True},
                "offerDetails": {"basePlanId": "monthly"},
            },
        ]
        response = self._sync(token, FakeGooglePlayClient({token: payload}))
        self.assertTrue(response.synced)
        self.assertEqual(response.plan, "catequista")
        self.assertEqual(response.active_product_id, "vf.sub.catequista")
        with self.session_factory() as db:
            items = db.query(BillingSubscriptionItem).order_by(BillingSubscriptionItem.id).all()
            self.assertEqual(len(items), 2)
            self.assertEqual(len({item.item_key for item in items}), 2)
            self.assertEqual([item.entitled for item in items], [True, False])

        renewed = self._payload(acknowledged=True)
        renewed["lineItems"] = [
            {
                "productId": "vf.sub.catequista",
                "expiryTime": (
                    datetime.datetime.utcnow() - datetime.timedelta(seconds=1)
                ).replace(microsecond=0).isoformat() + "Z",
                "latestSuccessfulOrderId": shared_order_id,
                "autoRenewingPlan": {"autoRenewEnabled": False},
                "offerDetails": {"basePlanId": "monthly"},
            },
            {
                "productId": "vf.sub.apologeta",
                "expiryTime": (
                    datetime.datetime.utcnow() + datetime.timedelta(days=30)
                ).replace(microsecond=0).isoformat() + "Z",
                "latestSuccessfulOrderId": shared_order_id,
                "autoRenewingPlan": {"autoRenewEnabled": True},
                "offerDetails": {"basePlanId": "monthly"},
            },
        ]
        renewed_response = self._sync(token, FakeGooglePlayClient({token: renewed}))
        self.assertTrue(renewed_response.synced)
        self.assertEqual(renewed_response.plan, "apologeta")
        with self.session_factory() as db:
            items = db.query(BillingSubscriptionItem).order_by(BillingSubscriptionItem.id).all()
            self.assertEqual([item.entitled for item in items], [False, True])

    def test_token_cannot_move_between_users_and_linked_token_is_replaced(self) -> None:
        old_token = "purchase-token-secret-linked-old"
        new_token = "purchase-token-secret-linked-new"
        self._sync(old_token, FakeGooglePlayClient({old_token: self._payload(acknowledged=True)}))
        pending = self._payload(
            state="SUBSCRIPTION_STATE_PENDING",
            linked_token=old_token,
        )
        self._sync(
            new_token,
            FakeGooglePlayClient({new_token: pending}),
        )
        with self.session_factory() as db:
            old = db.query(BillingSubscription).filter_by(
                purchase_token_hash=purchase_token_fingerprint(old_token)
            ).one()
            self.assertEqual(old.entitlement_state, "entitled")
            self.assertTrue(db.query(BillingSubscriptionItem).filter_by(
                billing_subscription_id=old.id
            ).one().entitled)
            self.assertEqual(db.get(User, 41).plan, "catequista")

        canceled_pending_token = "purchase-token-secret-linked-pending-canceled"
        canceled_pending = self._payload(
            state="SUBSCRIPTION_STATE_PENDING_PURCHASE_CANCELED",
            linked_token=old_token,
        )
        canceled_response = self._sync(
            canceled_pending_token,
            FakeGooglePlayClient({canceled_pending_token: canceled_pending}),
        )
        self.assertTrue(canceled_response.synced)
        self.assertFalse(canceled_response.results[0].entitlement_granted)
        with self.session_factory() as db:
            old = db.query(BillingSubscription).filter_by(
                purchase_token_hash=purchase_token_fingerprint(old_token)
            ).one()
            self.assertEqual(old.entitlement_state, "entitled")
            self.assertEqual(db.get(User, 41).plan, "catequista")

        self._sync(
            new_token,
            FakeGooglePlayClient(
                {new_token: self._payload(acknowledged=True, linked_token=old_token)}
            ),
        )
        with self.session_factory() as db:
            old = db.query(BillingSubscription).filter_by(
                purchase_token_hash=purchase_token_fingerprint(old_token)
            ).one()
            self.assertEqual(old.entitlement_state, "replaced")
            self.assertFalse(db.query(BillingSubscriptionItem).filter_by(
                billing_subscription_id=old.id
            ).one().entitled)
            db.add(
                User(
                    id=42,
                    email="other@example.com",
                    name="Other",
                    password_hash="unused",
                    plan="fiel",
                    is_active=True,
                )
            )
            db.commit()

        payload_without_account = self._payload(acknowledged=True)
        payload_without_account["externalAccountIdentifiers"] = {}
        with (
            patch.object(settings, "google_play_require_obfuscated_account_id", False),
            patch.object(routes, "SessionLocal", self.session_factory),
            patch.object(routes, "_require_enabled"),
            patch.object(
                routes,
                "get_google_play_client",
                return_value=FakeGooglePlayClient({new_token: payload_without_account}),
            ),
        ):
            response = routes.sync_google_play_subscriptions(
                routes.GooglePlayPurchaseBatch(purchases=[{"purchase_token": new_token}]),
                Response(),
                SimpleNamespace(id=42, email="other@example.com"),
            )
        self.assertFalse(response.synced)
        self.assertEqual(response.results[0].state, "ownership_conflict")

    def test_restore_indexes_duplicates_without_echoing_tokens(self) -> None:
        token = "purchase-token-secret-0004"
        client = FakeGooglePlayClient({token: self._payload(acknowledged=True)})
        batch = routes.GooglePlayPurchaseBatch(
            purchases=[{"purchase_token": token}, {"purchase_token": token}]
        )
        with (
            patch.object(routes, "SessionLocal", self.session_factory),
            patch.object(routes, "_require_enabled"),
            patch.object(routes, "get_google_play_client", return_value=client),
        ):
            http_response = Response()
            response = routes.restore_google_play_subscriptions(
                batch,
                http_response,
                self.current_user,
            )
        self.assertFalse(response.restored)
        self.assertEqual([result.index for result in response.results], [0, 1])
        self.assertTrue(response.results[0].finish_transaction)
        self.assertEqual(response.results[1].state, "duplicate_input")
        self.assertEqual(client.get_calls, [token])
        self.assertNotIn(token, json.dumps(response.model_dump()))
        self.assertEqual(http_response.headers["cache-control"], "no-store, max-age=0")

    def test_out_of_app_resubscribe_uses_only_stored_expired_identity(self) -> None:
        old_token = "purchase-token-secret-out-of-app-old"
        new_token = "purchase-token-secret-out-of-app-new"
        self._sync(old_token, FakeGooglePlayClient({old_token: self._payload(acknowledged=True)}))
        out_of_app = self._payload(acknowledged=True)
        out_of_app["externalAccountIdentifiers"] = {}
        out_of_app["outOfAppPurchaseContext"] = {"expiredPurchaseToken": old_token}
        response = self._sync(new_token, FakeGooglePlayClient({new_token: out_of_app}))
        self.assertTrue(response.synced)
        self.assertTrue(response.results[0].entitlement_granted)
        self.assertNotIn(old_token, json.dumps(response.model_dump()))
        self.assertNotIn(new_token, json.dumps(response.model_dump()))

        with self.session_factory() as db:
            db.add(
                User(
                    id=42,
                    email="other-out-of-app@example.com",
                    name="Other",
                    password_hash="unused",
                    plan="fiel",
                    is_active=True,
                )
            )
            db.commit()
        conflicting_token = "purchase-token-secret-out-of-app-conflict"
        conflict_payload = self._payload(acknowledged=True)
        conflict_payload["externalAccountIdentifiers"] = {}
        conflict_payload["outOfAppPurchaseContext"] = {"expiredPurchaseToken": old_token}
        conflict = self._sync(
            conflicting_token,
            FakeGooglePlayClient({conflicting_token: conflict_payload}),
            current_user=SimpleNamespace(id=42, email="other-out-of-app@example.com"),
        )
        self.assertFalse(conflict.synced)
        self.assertEqual(conflict.results[0].state, "ownership_conflict")

    def test_state_matrix_is_fail_closed(self) -> None:
        future = datetime.datetime.utcnow() + datetime.timedelta(days=1)
        past = datetime.datetime.utcnow() - datetime.timedelta(days=1)
        expected = {
            "SUBSCRIPTION_STATE_ACTIVE": "entitled",
            "SUBSCRIPTION_STATE_IN_GRACE_PERIOD": "grace",
            "SUBSCRIPTION_STATE_PAUSED": "paused",
            "SUBSCRIPTION_STATE_ON_HOLD": "hold",
            "SUBSCRIPTION_STATE_PENDING": "pending",
            "SUBSCRIPTION_STATE_EXPIRED": "inactive",
            "SUBSCRIPTION_STATE_PENDING_PURCHASE_CANCELED": "inactive",
            "SUBSCRIPTION_STATE_UNSPECIFIED": "inactive",
        }
        for provider_state, entitlement_state in expected.items():
            with self.subTest(provider_state=provider_state):
                self.assertEqual(
                    entitlement_state_for_google(provider_state, future),
                    entitlement_state,
                )
        self.assertEqual(entitlement_state_for_google("SUBSCRIPTION_STATE_CANCELED", future), "canceled_valid")
        self.assertEqual(entitlement_state_for_google("SUBSCRIPTION_STATE_CANCELED", past), "inactive")

    def test_billing_status_returns_authoritative_period_for_current_and_expired_cancellation(self) -> None:
        future = datetime.datetime.utcnow() + datetime.timedelta(days=7)
        past = datetime.datetime.utcnow() - datetime.timedelta(seconds=1)
        with self.session_factory() as db:
            user = db.get(User, 41)
            record_stripe_projection(
                db,
                user=user,
                subscription_id="sub_canceled_period",
                customer_id="cus_canceled_period",
                status_value="canceled",
                plan="catequista",
                current_period_end=future,
                cancel_at_period_end=True,
            )
            db.commit()

        with (
            patch.object(routes, "SessionLocal", self.session_factory),
            patch.object(
                routes,
                "lock_user_for_billing_mutation",
                wraps=lock_user_for_billing_mutation,
            ) as user_lock,
        ):
            current = routes.billing_status(Response(), self.current_user)
        self.assertEqual(current.plan, "catequista")
        self.assertEqual(current.billing_status, "canceled")
        self.assertEqual(current.billing_provider, "stripe")
        self.assertEqual(current.current_period_end, future)
        user_lock.assert_called_once()
        self.assertEqual(user_lock.call_args.args[1], 41)

        with self.session_factory() as db:
            subscription = db.query(BillingSubscription).filter_by(
                external_subscription_id="sub_canceled_period"
            ).one()
            subscription.current_period_end = past
            subscription.items[0].expiry_time = past
            db.commit()
        with patch.object(routes, "SessionLocal", self.session_factory):
            expired = routes.billing_status(Response(), self.current_user)
        self.assertEqual(expired.plan, "fiel")
        self.assertEqual(expired.billing_status, "canceled")
        self.assertEqual(expired.billing_provider, "stripe")
        self.assertEqual(expired.current_period_end, past)

    def test_expired_checkout_pending_is_terminal_in_status_and_not_recoverable(self) -> None:
        past = datetime.datetime.utcnow() - datetime.timedelta(minutes=1)
        with self.session_factory() as db:
            user = db.get(User, 41)
            upsert_subscription(
                db,
                user=user,
                provider="stripe",
                package_name="",
                provider_status="checkout_pending",
                entitlement_state="pending",
                external_subscription_id="cs_expired_preflight",
                provider_customer_id="cus_expired_preflight",
                current_period_end=past,
                items=[
                    SubscriptionItemInput(
                        item_key="stripe-checkout:catequista",
                        product_id="stripe:catequista",
                        plan="catequista",
                        expiry_time=past,
                        entitled=False,
                    )
                ],
            )
            resolved = recompute_user_plan(db, user)
            self.assertFalse(
                has_recoverable_provider_subscription(
                    db,
                    user_id=user.id,
                    provider="stripe",
                )
            )
            db.commit()

        self.assertEqual(resolved.plan, "fiel")
        self.assertEqual(resolved.billing_status, "checkout_expired")
        self.assertEqual(resolved.provider, "stripe")
        self.assertEqual(resolved.current_period_end, past)
        with patch.object(routes, "SessionLocal", self.session_factory):
            response = routes.billing_status(Response(), self.current_user)
        self.assertEqual(response.billing_status, "checkout_expired")
        self.assertEqual(response.current_period_end, past)

    def test_owner_status_has_no_period_and_google_play_purchase_is_disabled(self) -> None:
        owner = SimpleNamespace(id=99, email="owner-play-test@example.com")
        with self.session_factory() as db:
            db.add(
                User(
                    id=owner.id,
                    email=owner.email,
                    name="Owner",
                    password_hash="unused",
                    plan="fiel",
                    is_active=True,
                    email_verified=True,
                )
            )
            db.commit()

        with (
            patch.object(settings, "owner_email", owner.email),
            patch.object(routes, "SessionLocal", self.session_factory),
        ):
            status_response = routes.billing_status(Response(), owner)
            with patch.object(routes, "_require_enabled") as require_enabled:
                catalog_response = routes.google_play_catalog(Response(), owner)
            with (
                patch.object(routes, "get_google_play_client") as get_client,
                self.assertRaises(HTTPException) as blocked,
            ):
                routes.sync_google_play_subscriptions(
                    routes.GooglePlayPurchaseBatch(
                        purchases=[{"purchase_token": "owner-purchase-token-blocked"}]
                    ),
                    Response(),
                    owner,
                )

        self.assertEqual(status_response.plan, "magisterio")
        self.assertEqual(status_response.billing_status, "owner")
        self.assertIsNone(status_response.billing_provider)
        self.assertIsNone(status_response.current_period_end)
        self.assertFalse(catalog_response.enabled)
        self.assertEqual(catalog_response.products, [])
        self.assertIsNone(catalog_response.obfuscated_account_id)
        require_enabled.assert_not_called()
        self.assertEqual(blocked.exception.status_code, 403)
        get_client.assert_not_called()

    def test_unified_resolver_keeps_highest_entitlement_across_providers(self) -> None:
        token = "purchase-token-secret-0005"
        self._sync(token, FakeGooglePlayClient({token: self._payload()}))
        with self.session_factory() as db:
            user = db.get(User, 41)
            record_stripe_projection(
                db,
                user=user,
                subscription_id="sub_high",
                customer_id="cus_high",
                status_value="active",
                plan="magisterio",
                current_period_end=datetime.datetime.utcnow() + datetime.timedelta(days=20),
                cancel_at_period_end=False,
            )
            resolved = recompute_user_plan(db, user)
            db.commit()
            self.assertEqual(resolved.plan, "magisterio")
            self.assertEqual(resolved.provider, "stripe")

            stripe = db.query(BillingSubscription).filter_by(provider="stripe").one()
            stripe_item = db.query(BillingSubscriptionItem).filter_by(
                billing_subscription_id=stripe.id
            ).one()
            stripe_item.plan = "catequista"
            resolved = recompute_user_plan(db, user)
            self.assertEqual(resolved.plan, "catequista")
            self.assertEqual(resolved.provider, "google_play")

            stripe.entitlement_state = "inactive"
            db.query(BillingSubscriptionItem).filter_by(
                billing_subscription_id=stripe.id
            ).update({BillingSubscriptionItem.entitled: False})
            resolved = recompute_user_plan(db, user)
            self.assertEqual(resolved.plan, "catequista")
            self.assertEqual(resolved.provider, "google_play")

    def test_provider_conflict_blocks_only_new_play_token_and_blocks_stripe_checkout(self) -> None:
        existing_token = "purchase-token-secret-provider-existing"
        existing_payload = self._payload(acknowledged=True)
        self._sync(
            existing_token,
            FakeGooglePlayClient({existing_token: existing_payload}),
        )
        with self.session_factory() as db:
            user = db.get(User, 41)
            record_stripe_projection(
                db,
                user=user,
                subscription_id="sub_provider_conflict",
                customer_id="cus_provider_conflict",
                status_value="active",
                plan="apologeta",
                current_period_end=datetime.datetime.utcnow() + datetime.timedelta(days=20),
                cancel_at_period_end=False,
            )
            db.commit()

        existing_client = FakeGooglePlayClient({existing_token: existing_payload})
        refreshed = self._sync(existing_token, existing_client)
        self.assertTrue(refreshed.synced)
        self.assertEqual(existing_client.get_calls, [existing_token])

        new_token = "purchase-token-secret-provider-new"
        new_client = FakeGooglePlayClient({new_token: self._payload(acknowledged=True)})
        blocked = self._sync(new_token, new_client)
        self.assertFalse(blocked.synced)
        self.assertEqual(blocked.results[0].state, "provider_conflict")
        self.assertFalse(blocked.results[0].finish_transaction)
        self.assertEqual(new_client.get_calls, [])

        fake_stripe = Mock()
        with (
            patch.object(stripe_routes, "SessionLocal", self.session_factory),
            patch.object(stripe_routes, "stripe", fake_stripe),
            self.assertRaises(HTTPException) as checkout_blocked,
        ):
            stripe_routes.create_checkout_session(
                stripe_routes.CheckoutRequest(plan="catequista"),
                self.current_user,
            )
        self.assertEqual(checkout_blocked.exception.status_code, 409)
        fake_stripe.checkout.Session.create.assert_not_called()

    def test_stripe_checkout_records_pending_intent_before_play_can_sync(self) -> None:
        expiry = int((datetime.datetime.utcnow() + datetime.timedelta(hours=2)).timestamp())
        fake_stripe = Mock()
        fake_stripe.error.StripeError = Exception
        fake_stripe.Customer.create.return_value = {"id": "cus_checkout_intent"}
        fake_stripe.checkout.Session.list.return_value = {"data": []}
        fake_stripe.checkout.Session.retrieve.return_value = {
            "id": "cs_checkout_intent",
            "status": "open",
        }
        fake_stripe.checkout.Session.create.return_value = {
            "id": "cs_checkout_intent",
            "url": "https://checkout.stripe.example/session",
            "expires_at": expiry,
        }
        with (
            patch.object(stripe_routes, "SessionLocal", self.session_factory),
            patch.object(stripe_routes, "stripe", fake_stripe),
            patch.object(settings, "billing_provider", "stripe"),
            patch.object(settings, "stripe_secret_key", "sk_test_redacted"),
            patch.object(settings, "stripe_price_catequista", "price_catequista"),
        ):
            response = stripe_routes.create_checkout_session(
                stripe_routes.CheckoutRequest(plan="catequista"),
                self.current_user,
            )
            with self.assertRaises(HTTPException) as repeated:
                stripe_routes.create_checkout_session(
                    stripe_routes.CheckoutRequest(plan="catequista"),
                    self.current_user,
                )
        self.assertEqual(response.url, "https://checkout.stripe.example/session")
        self.assertEqual(repeated.exception.status_code, 409)
        fake_stripe.checkout.Session.create.assert_called_once()
        create_kwargs = fake_stripe.checkout.Session.create.call_args.kwargs
        self.assertRegex(
            create_kwargs["idempotency_key"],
            r"^vf-checkout-v1-41-catequista-[0-9a-f]{32}$",
        )
        self.assertNotIn("reader@example.com", create_kwargs["idempotency_key"])
        self.assertEqual(
            fake_stripe.Customer.create.call_args.kwargs["idempotency_key"],
            "vf-customer-v1-41",
        )
        with self.session_factory() as db:
            intent = db.query(BillingSubscription).filter_by(provider="stripe").one()
            self.assertEqual(intent.provider_status, "checkout_pending")
            self.assertEqual(intent.entitlement_state, "pending")
            self.assertEqual(intent.external_subscription_id, "cs_checkout_intent")
            self.assertLessEqual(
                intent.current_period_end,
                datetime.datetime.utcnow() + datetime.timedelta(hours=24),
            )

        play_token = "purchase-token-secret-after-checkout-intent"
        play_client = FakeGooglePlayClient({play_token: self._payload(acknowledged=True)})
        blocked = self._sync(play_token, play_client)
        self.assertFalse(blocked.synced)
        self.assertEqual(blocked.results[0].state, "provider_conflict")
        self.assertEqual(play_client.get_calls, [])

        with self.session_factory() as db:
            intent = db.query(BillingSubscription).filter_by(provider="stripe").one()
            intent.current_period_end = datetime.datetime.utcnow() - datetime.timedelta(seconds=1)
            db.commit()
        allowed_client = FakeGooglePlayClient({play_token: self._payload(acknowledged=True)})
        allowed = self._sync(play_token, allowed_client)
        self.assertTrue(allowed.synced)
        self.assertEqual(allowed_client.get_calls, [play_token])

    def test_expired_checkout_can_start_a_new_attempt_with_a_new_idempotency_key(self) -> None:
        expiry = int((datetime.datetime.utcnow() + datetime.timedelta(hours=2)).timestamp())
        fake_stripe = Mock()
        fake_stripe.error.StripeError = Exception
        fake_stripe.Customer.create.return_value = {"id": "cus_checkout_retry"}
        fake_stripe.checkout.Session.list.return_value = {"data": []}
        fake_stripe.checkout.Session.retrieve.return_value = {
            "id": "cs_checkout_first",
            "status": "expired",
        }
        fake_stripe.checkout.Session.create.side_effect = [
            {
                "id": "cs_checkout_first",
                "url": "https://checkout.stripe.example/first",
                "expires_at": expiry,
            },
            {
                "id": "cs_checkout_second",
                "url": "https://checkout.stripe.example/second",
                "expires_at": expiry,
            },
        ]
        with (
            patch.object(stripe_routes, "SessionLocal", self.session_factory),
            patch.object(stripe_routes, "stripe", fake_stripe),
            patch.object(settings, "billing_provider", "stripe"),
            patch.object(settings, "stripe_secret_key", "sk_test_redacted"),
            patch.object(settings, "stripe_price_catequista", "price_catequista"),
        ):
            first = stripe_routes.create_checkout_session(
                stripe_routes.CheckoutRequest(plan="catequista"),
                self.current_user,
            )
            second = stripe_routes.create_checkout_session(
                stripe_routes.CheckoutRequest(plan="catequista"),
                self.current_user,
            )

        self.assertTrue(first.url.endswith("/first"))
        self.assertTrue(second.url.endswith("/second"))
        keys = [call.kwargs["idempotency_key"] for call in fake_stripe.checkout.Session.create.call_args_list]
        self.assertEqual(len(keys), 2)
        self.assertNotEqual(keys[0], keys[1])
        with self.session_factory() as db:
            states = {
                row.external_subscription_id: row.provider_status
                for row in db.query(BillingSubscription).filter_by(provider="stripe").all()
            }
        self.assertEqual(states["cs_checkout_first"], "checkout_expired")
        self.assertEqual(states["cs_checkout_second"], "checkout_pending")

    def test_completed_checkout_without_authoritative_subscription_blocks_retry(self) -> None:
        expiry = int((datetime.datetime.utcnow() + datetime.timedelta(hours=2)).timestamp())
        fake_stripe = Mock()
        fake_stripe.error.StripeError = Exception
        fake_stripe.error.InvalidRequestError = type("InvalidRequestError", (Exception,), {})
        fake_stripe.Customer.create.return_value = {"id": "cus_checkout_complete"}
        fake_stripe.checkout.Session.list.return_value = {"data": []}
        fake_stripe.checkout.Session.retrieve.return_value = {
            "id": "cs_checkout_complete",
            "status": "complete",
        }
        fake_stripe.checkout.Session.create.return_value = {
            "id": "cs_checkout_complete",
            "url": "https://checkout.stripe.example/complete",
            "expires_at": expiry,
        }
        fake_stripe.Subscription.list.return_value = {"data": []}
        with (
            patch.object(stripe_routes, "SessionLocal", self.session_factory),
            patch.object(stripe_routes, "stripe", fake_stripe),
            patch.object(settings, "billing_provider", "stripe"),
            patch.object(settings, "stripe_secret_key", "sk_test_redacted"),
            patch.object(settings, "stripe_price_catequista", "price_catequista"),
        ):
            stripe_routes.create_checkout_session(
                stripe_routes.CheckoutRequest(plan="catequista"),
                self.current_user,
            )
            with self.assertRaises(HTTPException) as blocked:
                stripe_routes.create_checkout_session(
                    stripe_routes.CheckoutRequest(plan="catequista"),
                    self.current_user,
                )

        self.assertEqual(blocked.exception.status_code, 409)
        fake_stripe.checkout.Session.create.assert_called_once()

    def test_sync_restore_rate_limit_counts_tokens_and_catalog_does_not_consume(self) -> None:
        tokens = [
            "purchase-token-rate-limit-one",
            "purchase-token-rate-limit-two",
            "purchase-token-rate-limit-three",
        ]
        client = FakeGooglePlayClient(
            {token: self._payload(acknowledged=True) for token in tokens}
        )
        with (
            patch.object(routes, "SessionLocal", self.session_factory),
            patch.object(routes, "_require_enabled"),
        ):
            for _ in range(5):
                routes.google_play_catalog(Response(), self.current_user)
        with self.session_factory() as db:
            self.assertEqual(db.query(BillingRateLimit).count(), 0)

        with (
            patch.object(routes, "SessionLocal", self.session_factory),
            patch.object(routes, "_require_enabled"),
            patch.object(routes, "get_google_play_client", return_value=client),
            patch.object(settings, "google_play_sync_rate_limit", 2),
            patch.object(settings, "google_play_sync_rate_window_seconds", 60),
        ):
            synced = routes.sync_google_play_subscriptions(
                routes.GooglePlayPurchaseBatch(
                    purchases=[
                        {"purchase_token": tokens[0]},
                        {"purchase_token": tokens[1]},
                    ]
                ),
                Response(),
                self.current_user,
            )
            blocked_response = Response()
            with self.assertRaises(HTTPException) as blocked:
                routes.restore_google_play_subscriptions(
                    routes.GooglePlayPurchaseBatch(
                        purchases=[{"purchase_token": tokens[2]}]
                    ),
                    blocked_response,
                    self.current_user,
                )

            self.assertTrue(synced.synced)
            self.assertEqual(blocked.exception.status_code, 429)
            self.assertGreaterEqual(int(blocked.exception.headers["Retry-After"]), 1)
            self.assertEqual(blocked_response.headers["Cache-Control"], "no-store, max-age=0")
            self.assertEqual(client.get_calls, tokens[:2])

            with self.session_factory() as db:
                limiter = db.query(BillingRateLimit).one()
                self.assertEqual(limiter.attempts, 2)
                limiter.window_started_at = datetime.datetime.utcnow() - datetime.timedelta(seconds=61)
                db.commit()

            restored = routes.restore_google_play_subscriptions(
                routes.GooglePlayPurchaseBatch(
                    purchases=[{"purchase_token": tokens[2]}]
                ),
                Response(),
                self.current_user,
            )

        self.assertTrue(restored.restored)
        self.assertEqual(client.get_calls, tokens)
        with self.session_factory() as db:
            self.assertEqual(db.query(BillingRateLimit).one().attempts, 1)

    def test_sync_batch_uses_one_commit_and_failure_does_not_discard_later_valid_item(self) -> None:
        failed_token = "purchase-token-secret-batch-failed"
        valid_token = "purchase-token-secret-batch-valid"
        client = FakeGooglePlayClient(
            {
                failed_token: GooglePlayAPIError("invalid", retryable=False, status_code=404),
                valid_token: self._payload(acknowledged=True),
            }
        )
        commits: list[int] = []

        def counting_factory():
            db = self.session_factory()
            original_commit = db.commit

            def counted_commit():
                commits.append(1)
                return original_commit()

            db.commit = counted_commit
            return db

        lock_events: list[str] = []

        def locking(db, user_id):
            lock_events.append("lock")
            return lock_user_for_billing_mutation(db, user_id)

        original_get = client.get_subscription

        def tracked_get(token):
            lock_events.append(f"get:{token}")
            return original_get(token)

        client.get_subscription = tracked_get
        with (
            patch.object(routes, "SessionLocal", counting_factory),
            patch.object(routes, "_require_enabled"),
            patch.object(routes, "get_google_play_client", return_value=client),
            patch.object(routes, "lock_user_for_billing_mutation", side_effect=locking),
        ):
            response = routes.sync_google_play_subscriptions(
                routes.GooglePlayPurchaseBatch(
                    purchases=[
                        {"purchase_token": failed_token},
                        {"purchase_token": valid_token},
                    ]
                ),
                Response(),
                self.current_user,
            )
        self.assertFalse(response.synced)
        self.assertEqual([row.accepted for row in response.results], [False, True])
        self.assertEqual(commits, [1])
        self.assertEqual(lock_events[0], "lock")
        self.assertEqual(lock_events.count("lock"), 1)
        with self.session_factory() as db:
            subscriptions = db.query(BillingSubscription).filter_by(provider="google_play").all()
            self.assertEqual(len(subscriptions), 1)
            self.assertEqual(
                subscriptions[0].purchase_token_hash,
                purchase_token_fingerprint(valid_token),
            )

    def test_restart_backfill_never_turns_play_access_into_permanent_legacy_access(self) -> None:
        token = "purchase-token-secret-backfill-regression"
        self._sync(token, FakeGooglePlayClient({token: self._payload(acknowledged=True)}))
        with patch.object(database_models, "SessionLocal", self.session_factory):
            database_models._backfill_legacy_billing_subscriptions()
        with self.session_factory() as db:
            self.assertEqual(db.query(BillingSubscription).count(), 1)
            self.assertEqual(db.get(User, 41).plan, "catequista")
            subscription = db.query(BillingSubscription).one()
            subscription.entitlement_state = "revoked"
            subscription.provider_status = "SUBSCRIPTION_REVOKED"
            db.query(BillingSubscriptionItem).filter_by(
                billing_subscription_id=subscription.id
            ).update({BillingSubscriptionItem.entitled: False})
            recompute_user_plan(db, db.get(User, 41))
            db.commit()

        with patch.object(database_models, "SessionLocal", self.session_factory):
            database_models._backfill_legacy_billing_subscriptions()
        with self.session_factory() as db:
            self.assertEqual(db.query(BillingSubscription).count(), 1)
            self.assertEqual(db.query(BillingSubscription).one().provider, "google_play")
            self.assertEqual(db.get(User, 41).plan, "fiel")

    def test_session_gate_downgrades_locally_expired_ledger_without_provider(self) -> None:
        token = "purchase-token-secret-session-expiry"
        self._sync(token, FakeGooglePlayClient({token: self._payload(acknowledged=True)}))
        with self.session_factory() as db:
            item = db.query(BillingSubscriptionItem).one()
            item.expiry_time = datetime.datetime.utcnow() - datetime.timedelta(seconds=1)
            self.assertEqual(db.get(User, 41).plan, "catequista")
            db.commit()

        with patch.object(deps, "_get_db", self.session_factory):
            loaded = deps._get_user_by_id(41)
        self.assertEqual(loaded.plan, "fiel")
        with self.session_factory() as db:
            self.assertEqual(db.get(User, 41).plan, "fiel")

    def test_api_key_gate_downgrades_expired_magisterio_before_authorizing(self) -> None:
        token = "purchase-token-secret-api-key-expiry"
        payload = self._payload(product_id="vf.sub.magisterio", acknowledged=True)
        self._sync(token, FakeGooglePlayClient({token: payload}))
        raw_api_key = "vf_live_api_key_secret"
        with self.session_factory() as db:
            item = db.query(BillingSubscriptionItem).one()
            item.expiry_time = datetime.datetime.utcnow() - datetime.timedelta(seconds=1)
            db.add(
                ApiKey(
                    user_id=41,
                    key_hash=hashlib.sha256(raw_api_key.encode()).hexdigest(),
                    label="test",
                    is_active=True,
                )
            )
            db.commit()

        with (
            patch.object(api_key_auth, "SessionLocal", self.session_factory),
            self.assertRaises(HTTPException) as rejected,
        ):
            api_key_auth.require_vf_api_key(raw_api_key)
        self.assertEqual(rejected.exception.status_code, 403)
        with self.session_factory() as db:
            self.assertEqual(db.get(User, 41).plan, "fiel")
            self.assertEqual(db.query(ApiKey).one().usage_count, 0)

    async def test_voided_rtdn_revokes_without_provider_lookup_and_replay_hash_is_fixed(self) -> None:
        token = "purchase-token-secret-0006"
        client = FakeGooglePlayClient({token: self._payload()})
        self._sync(token, client)
        notification = {
            "version": "1.0",
            "packageName": "com.verafidei.app",
            "eventTimeMillis": "1800000000000",
            "voidedPurchaseNotification": {"purchaseToken": token, "orderId": "GPA.redacted"},
        }
        envelope = {
            "subscription": "projects/project/subscriptions/vera-rtdn",
            "message": {
                "messageId": "message-void-1",
                "data": base64.b64encode(json.dumps(notification).encode()).decode(),
            },
        }
        body = json.dumps(envelope).encode()
        with (
            patch.object(routes, "SessionLocal", self.session_factory),
            patch.object(routes, "_require_enabled"),
            patch.object(routes, "_verify_pubsub_oidc", return_value={"email_verified": True}),
            patch.object(routes, "get_google_play_client", return_value=Mock()) as get_client,
        ):
            response = await routes.google_play_rtdn(BodyRequest(body), "Bearer signed")
            self.assertEqual(response.status_code, 204)
            get_client.assert_not_called()
            duplicate = await routes.google_play_rtdn(BodyRequest(body), "Bearer signed")
            self.assertEqual(duplicate.status_code, 204)

            delivery_retry = json.loads(body)
            delivery_retry["deliveryAttempt"] = 2
            retried = await routes.google_play_rtdn(
                BodyRequest(json.dumps(delivery_retry).encode()),
                "Bearer signed",
            )
            self.assertEqual(retried.status_code, 204)

            changed = json.loads(body)
            changed["message"]["data"] = base64.b64encode(
                json.dumps({**notification, "eventTimeMillis": "1800000000001"}).encode()
            ).decode()
            with self.assertRaises(HTTPException) as replay_error:
                await routes.google_play_rtdn(
                    BodyRequest(json.dumps(changed).encode()),
                    "Bearer signed",
                )
            self.assertEqual(replay_error.exception.status_code, 409)

        with self.session_factory() as db:
            subscription = db.query(BillingSubscription).filter_by(provider="google_play").one()
            user = db.get(User, 41)
            event = db.query(BillingEvent).one()
            self.assertEqual(subscription.entitlement_state, "revoked")
            self.assertEqual(user.plan, "fiel")
            self.assertEqual(event.status, "processed")
            self.assertNotIn(token, event.payload_sha256)

    async def test_revoked_rtdn_404_still_revokes_local_entitlement(self) -> None:
        token = "purchase-token-secret-revoked-404"
        self._sync(token, FakeGooglePlayClient({token: self._payload()}))
        notification = {
            "version": "1.0",
            "packageName": "com.verafidei.app",
            "eventTimeMillis": "1800000000000",
            "subscriptionNotification": {
                "notificationType": 12,
                "purchaseToken": token,
                "subscriptionId": "vf.sub.catequista",
            },
        }
        envelope = {
            "subscription": "projects/project/subscriptions/vera-rtdn",
            "message": {
                "messageId": "message-revoked-404",
                "data": base64.b64encode(json.dumps(notification).encode()).decode(),
            },
        }
        failing_client = FakeGooglePlayClient(
            {
                token: GooglePlayAPIError(
                    "not found",
                    retryable=False,
                    status_code=404,
                )
            }
        )
        with (
            patch.object(routes, "SessionLocal", self.session_factory),
            patch.object(routes, "_require_enabled"),
            patch.object(routes, "_verify_pubsub_oidc", return_value={"email_verified": True}),
            patch.object(routes, "get_google_play_client", return_value=failing_client),
        ):
            response = await routes.google_play_rtdn(
                BodyRequest(json.dumps(envelope).encode()),
                "Bearer signed",
            )
        self.assertEqual(response.status_code, 204)
        with self.session_factory() as db:
            subscription = db.query(BillingSubscription).filter_by(provider="google_play").one()
            event = db.query(BillingEvent).filter_by(event_id="message-revoked-404").one()
            self.assertEqual(subscription.entitlement_state, "revoked")
            self.assertEqual(db.get(User, 41).plan, "fiel")
            self.assertEqual(event.status, "processed")

    async def test_expired_rtdn_410_inactivates_local_entitlement(self) -> None:
        token = "purchase-token-secret-expired-410"
        self._sync(token, FakeGooglePlayClient({token: self._payload()}))
        failing_client = FakeGooglePlayClient(
            {
                token: GooglePlayAPIError(
                    "gone",
                    retryable=False,
                    status_code=410,
                )
            }
        )
        with (
            patch.object(routes, "SessionLocal", self.session_factory),
            patch.object(routes, "_require_enabled"),
            patch.object(routes, "_verify_pubsub_oidc", return_value={"email_verified": True}),
            patch.object(routes, "get_google_play_client", return_value=failing_client),
        ):
            response = await routes.google_play_rtdn(
                BodyRequest(
                    self._subscription_envelope(
                        token=token,
                        notification_type=13,
                        message_id="message-expired-410",
                    )
                ),
                "Bearer signed",
            )
        self.assertEqual(response.status_code, 204)
        with self.session_factory() as db:
            subscription = db.query(BillingSubscription).filter_by(provider="google_play").one()
            event = db.query(BillingEvent).filter_by(event_id="message-expired-410").one()
            self.assertEqual(subscription.entitlement_state, "inactive")
            self.assertEqual(subscription.provider_status, "SUBSCRIPTION_EXPIRED")
            self.assertEqual(db.get(User, 41).plan, "fiel")
            self.assertEqual(event.status, "processed")

    async def test_out_of_app_rtdn_resolves_expired_token_and_rejects_owner_conflict(self) -> None:
        old_token = "purchase-token-secret-rtdn-out-old"
        new_token = "purchase-token-secret-rtdn-out-new"
        self._sync(old_token, FakeGooglePlayClient({old_token: self._payload(acknowledged=True)}))
        out_payload = self._payload(acknowledged=False)
        out_payload["externalAccountIdentifiers"] = {}
        out_payload["outOfAppPurchaseContext"] = {"expiredPurchaseToken": old_token}
        client = FakeGooglePlayClient({new_token: out_payload})
        with (
            patch.object(routes, "SessionLocal", self.session_factory),
            patch.object(routes, "_require_enabled"),
            patch.object(routes, "_verify_pubsub_oidc", return_value={"email_verified": True}),
            patch.object(routes, "get_google_play_client", return_value=client),
        ):
            response = await routes.google_play_rtdn(
                BodyRequest(
                    self._subscription_envelope(
                        token=new_token,
                        notification_type=4,
                        message_id="message-out-of-app-known",
                    )
                ),
                "Bearer signed",
            )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(client.ack_calls, [(new_token, "vf.sub.catequista")])
        with self.session_factory() as db:
            new_subscription = db.query(BillingSubscription).filter_by(
                purchase_token_hash=purchase_token_fingerprint(new_token)
            ).one()
            event = db.query(BillingEvent).filter_by(event_id="message-out-of-app-known").one()
            self.assertEqual(new_subscription.user_id, 41)
            self.assertEqual(event.user_id, 41)
            self.assertEqual(event.status, "processed")

            db.add(
                User(
                    id=42,
                    email="rtdn-other@example.com",
                    name="Other",
                    password_hash="unused",
                    plan="fiel",
                    is_active=True,
                )
            )
            db.commit()
        other_old = "purchase-token-secret-rtdn-other-old"
        self._sync(
            other_old,
            FakeGooglePlayClient(
                {
                    other_old: self._payload(
                        acknowledged=True,
                        account_id=obfuscated_account_id(42),
                    )
                }
            ),
            current_user=SimpleNamespace(id=42, email="rtdn-other@example.com"),
        )
        conflicting_new = "purchase-token-secret-rtdn-owner-conflict"
        conflict_payload = self._payload(acknowledged=True)
        conflict_payload["outOfAppPurchaseContext"] = {"expiredPurchaseToken": other_old}
        conflict_client = FakeGooglePlayClient({conflicting_new: conflict_payload})
        with (
            patch.object(routes, "SessionLocal", self.session_factory),
            patch.object(routes, "_require_enabled"),
            patch.object(routes, "_verify_pubsub_oidc", return_value={"email_verified": True}),
            patch.object(routes, "get_google_play_client", return_value=conflict_client),
        ):
            conflict_response = await routes.google_play_rtdn(
                BodyRequest(
                    self._subscription_envelope(
                        token=conflicting_new,
                        notification_type=4,
                        message_id="message-out-of-app-conflict",
                    )
                ),
                "Bearer signed",
            )
        self.assertEqual(conflict_response.status_code, 204)
        with self.session_factory() as db:
            self.assertIsNone(
                db.query(BillingSubscription).filter_by(
                    purchase_token_hash=purchase_token_fingerprint(conflicting_new)
                ).first()
            )
            event = db.query(BillingEvent).filter_by(event_id="message-out-of-app-conflict").one()
            self.assertEqual(event.status, "rejected")
            self.assertEqual(event.last_error, "ownership_conflict")

    def test_catalog_requires_all_four_plans_when_enabled(self) -> None:
        with patch.object(settings, "google_play_products_json", json.dumps(PRODUCTS[:3])):
            with self.assertRaises(GooglePlayConfigurationError):
                load_product_catalog(strict=True)

        permuted = [dict(row) for row in PRODUCTS]
        permuted[0]["product_id"], permuted[1]["product_id"] = (
            permuted[1]["product_id"],
            permuted[0]["product_id"],
        )
        wrong_id = [dict(row) for row in PRODUCTS]
        wrong_id[0]["product_id"] = "vf.sub.not-catequista"
        wrong_base = [dict(row) for row in PRODUCTS]
        wrong_base[0]["base_plan_id"] = "annual"
        for invalid_catalog in (permuted, wrong_id, wrong_base):
            with self.subTest(invalid_catalog=invalid_catalog):
                with patch.object(
                    settings,
                    "google_play_products_json",
                    json.dumps(invalid_catalog),
                ):
                    with self.assertRaises(GooglePlayConfigurationError):
                        load_product_catalog(strict=True)

        with patch.object(settings, "google_play_enabled", False):
            http_response = Response()
            response = routes.google_play_catalog(http_response, self.current_user)
        self.assertFalse(response.enabled)
        self.assertEqual(response.products, [])
        self.assertEqual(http_response.headers["cache-control"], "no-store, max-age=0")

        with self.assertRaises(HTTPException) as missing_oidc:
            routes._verify_pubsub_oidc("")
        self.assertEqual(missing_oidc.exception.status_code, 401)

        with patch.object(settings, "google_play_require_obfuscated_account_id", False):
            with self.assertRaises(GooglePlayConfigurationError):
                validate_google_play_configuration()

    def test_configuration_rejects_unsafe_sync_rate_ranges(self) -> None:
        credential = json.dumps(
            {
                "client_email": "publisher@example.iam.gserviceaccount.com",
                "private_key": "redacted-test-key",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        )
        invalid_values = (
            ("google_play_sync_rate_limit", 0),
            ("google_play_sync_rate_limit", 121),
            ("google_play_sync_rate_window_seconds", 9),
            ("google_play_sync_rate_window_seconds", 3601),
        )
        with (
            patch.object(settings, "google_play_service_account_file", "credential.json"),
            patch.object(google_play_service.Path, "is_file", return_value=True),
            patch.object(google_play_service.Path, "read_text", return_value=credential),
        ):
            for setting_name, value in invalid_values:
                with self.subTest(setting_name=setting_name, value=value):
                    with (
                        patch.object(settings, setting_name, value),
                        self.assertRaises(GooglePlayConfigurationError),
                    ):
                        validate_google_play_configuration()

    async def test_invalid_request_validation_never_reflects_purchase_token(self) -> None:
        from core.http_security import sanitize_request_validation_error

        token = "invalid-purchase-token-that-must-not-be-reflected"
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "scheme": "https",
                "server": ("api.example", 443),
                "client": ("127.0.0.1", 1),
                "root_path": "",
                "path": "/billing/google-play/subscriptions/sync",
                "raw_path": b"/billing/google-play/subscriptions/sync",
                "query_string": b"",
                "headers": [],
            }
        )
        error = RequestValidationError(
            [
                {
                    "type": "string_too_short",
                    "loc": ("body", "purchases", 0, "purchase_token"),
                    "msg": "String should have at least 10 characters",
                    "input": token,
                }
            ]
        )
        response = await sanitize_request_validation_error(request, error)
        self.assertEqual(response.status_code, 422)
        self.assertNotIn(token, response.body.decode("utf-8"))
        self.assertEqual(response.headers["cache-control"], "no-store, max-age=0")

    async def test_rtdn_delegates_blocking_provider_and_database_work(self) -> None:
        expected = Response(status_code=204)

        async def fake_threadpool(function, *args):
            self.assertIs(function, routes._process_google_play_rtdn)
            self.assertEqual(args, (b"opaque-body", "Bearer signed"))
            return expected

        with patch.object(routes, "run_in_threadpool", side_effect=fake_threadpool) as delegated:
            response = await routes.google_play_rtdn(
                BodyRequest(b"opaque-body"),
                "Bearer signed",
            )
        self.assertIs(response, expected)
        delegated.assert_awaited_once()

    def test_reconciler_prioritizes_pending_ack_and_skips_fresh_acknowledged(self) -> None:
        token_pending = "purchase-token-secret-0007"
        token_fresh = "purchase-token-secret-0008"
        self._sync(
            token_pending,
            FakeGooglePlayClient({token_pending: self._payload(acknowledged=True)}),
        )
        self._sync(
            token_fresh,
            FakeGooglePlayClient({token_fresh: self._payload(acknowledged=True)}),
        )
        with self.session_factory() as db:
            subscriptions = db.query(BillingSubscription).order_by(BillingSubscription.id).all()
            subscriptions[0].acknowledgement_state = "ACKNOWLEDGEMENT_STATE_PENDING"
            now = datetime.datetime.utcnow()
            subscriptions[0].last_verified_at = now
            subscriptions[1].last_verified_at = now
            db.commit()

        fake = FakeGooglePlayClient({token_pending: self._payload(acknowledged=True)})
        with (
            patch.object(reconciler, "SessionLocal", self.session_factory),
            patch.object(reconciler, "validate_google_play_configuration"),
            patch.object(reconciler, "get_google_play_client", return_value=fake),
        ):
            result = reconciler.run(apply=False)
        self.assertEqual(result["checked"], 1)
        self.assertEqual(fake.get_calls, [token_pending])

    def test_reconciler_410_expires_only_when_local_expiry_has_passed(self) -> None:
        expired_token = "purchase-token-secret-reconcile-gone-expired"
        future_token = "purchase-token-secret-reconcile-gone-future"
        self._sync(
            expired_token,
            FakeGooglePlayClient({expired_token: self._payload(acknowledged=True)}),
        )
        self._sync(
            future_token,
            FakeGooglePlayClient({future_token: self._payload(acknowledged=True)}),
        )
        with self.session_factory() as db:
            rows = db.query(BillingSubscription).order_by(BillingSubscription.id).all()
            stale = datetime.datetime.utcnow() - datetime.timedelta(hours=7)
            rows[0].current_period_end = datetime.datetime.utcnow() - datetime.timedelta(seconds=1)
            rows[0].last_verified_at = stale
            rows[1].current_period_end = datetime.datetime.utcnow() + datetime.timedelta(days=1)
            rows[1].last_verified_at = stale
            db.query(BillingSubscriptionItem).filter_by(
                billing_subscription_id=rows[0].id
            ).update(
                {
                    BillingSubscriptionItem.expiry_time: datetime.datetime.utcnow()
                    - datetime.timedelta(seconds=1)
                }
            )
            db.commit()

        fake = FakeGooglePlayClient(
            {
                expired_token: GooglePlayAPIError(
                    "not found",
                    retryable=False,
                    status_code=404,
                ),
                future_token: GooglePlayAPIError(
                    "gone",
                    retryable=False,
                    status_code=410,
                ),
            }
        )
        lock_calls: list[int] = []

        def reconcile_lock(db, user_id):
            lock_calls.append(user_id)
            return lock_user_for_billing_mutation(db, user_id)

        with (
            patch.object(reconciler, "SessionLocal", self.session_factory),
            patch.object(reconciler, "validate_google_play_configuration"),
            patch.object(reconciler, "get_google_play_client", return_value=fake),
            patch.object(
                reconciler,
                "lock_user_for_billing_mutation",
                side_effect=reconcile_lock,
            ),
        ):
            result = reconciler.run(apply=True)
        self.assertEqual(result["checked"], 2)
        self.assertEqual(result["changed"], 1)
        self.assertEqual(len(result["errors"]), 1)
        self.assertEqual(lock_calls, [41])
        with self.session_factory() as db:
            expired = db.query(BillingSubscription).filter_by(
                purchase_token_hash=purchase_token_fingerprint(expired_token)
            ).one()
            future = db.query(BillingSubscription).filter_by(
                purchase_token_hash=purchase_token_fingerprint(future_token)
            ).one()
            self.assertEqual(expired.entitlement_state, "inactive")
            self.assertEqual(future.entitlement_state, "entitled")
            self.assertEqual(db.get(User, 41).plan, "catequista")

    def test_unified_reconciler_skips_disabled_providers_without_failure(self) -> None:
        with (
            patch.object(settings, "google_play_enabled", False),
            patch.object(settings, "stripe_secret_key", ""),
            patch.object(
                unified_reconciler.reconcile_google_play_subscriptions,
                "run",
                wraps=reconciler.run,
            ) as google_run,
        ):
            result = unified_reconciler.run(apply=False)
        self.assertTrue(result["stripe"]["skipped"])
        self.assertFalse(result["google_play"]["enabled"])
        self.assertEqual(result["google_play"]["errors"], [])
        google_run.assert_called_once_with(apply=False)

    def test_account_deletion_revalidates_stale_google_state_and_fails_closed(self) -> None:
        token = "purchase-token-secret-0009"
        client = FakeGooglePlayClient({token: self._payload()})
        self._sync(token, FakeGooglePlayClient({token: self._payload()}))
        with self.session_factory() as db:
            subscription = db.query(BillingSubscription).filter_by(provider="google_play").one()
            subscription.entitlement_state = "inactive"
            db.query(BillingSubscriptionItem).filter_by(
                billing_subscription_id=subscription.id
            ).update({BillingSubscriptionItem.entitled: False})
            db.commit()

        with self.session_factory() as db:
            user = db.get(User, 41)
            with (
                patch.object(auth, "validate_google_play_configuration"),
                patch.object(auth, "get_google_play_client", return_value=client),
                self.assertRaises(HTTPException) as live_error,
            ):
                auth._ensure_no_live_google_play_subscription(db, user)
        self.assertEqual(live_error.exception.status_code, 409)
        self.assertEqual(client.get_calls, [token])

        with self.session_factory() as db:
            user = db.get(User, 41)
            with (
                patch.object(auth, "validate_google_play_configuration"),
                patch.object(auth, "get_google_play_client", side_effect=RuntimeError("offline")),
                self.assertLogs(auth.logger.name, level="ERROR") as captured,
                self.assertRaises(HTTPException) as unavailable,
            ):
                auth._ensure_no_live_google_play_subscription(db, user)
        self.assertEqual(unavailable.exception.status_code, 503)
        self.assertTrue(
            any("google_play_account_deletion_check_failed" in line for line in captured.output)
        )

        gone_client = FakeGooglePlayClient(
            {token: GooglePlayAPIError("gone", retryable=False, status_code=410)}
        )
        with self.session_factory() as db:
            user = db.get(User, 41)
            with (
                patch.object(auth, "validate_google_play_configuration"),
                patch.object(auth, "get_google_play_client", return_value=gone_client),
            ):
                rows = auth._ensure_no_live_google_play_subscription(db, user)
            self.assertEqual(len(rows), 1)

        with self.session_factory() as db:
            subscription = db.query(BillingSubscription).one()
            subscription.entitlement_state = "entitled"
            subscription.current_period_end = datetime.datetime.utcnow() + datetime.timedelta(days=1)
            db.query(BillingSubscriptionItem).filter_by(
                billing_subscription_id=subscription.id
            ).update({BillingSubscriptionItem.entitled: True})
            db.commit()
        with self.session_factory() as db:
            user = db.get(User, 41)
            with (
                patch.object(auth, "validate_google_play_configuration"),
                patch.object(auth, "get_google_play_client", return_value=gone_client),
                self.assertLogs(auth.logger.name, level="ERROR"),
                self.assertRaises(HTTPException) as recoverable_gone,
            ):
                auth._ensure_no_live_google_play_subscription(db, user)
        self.assertEqual(recoverable_gone.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
