from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.routes import billing
from core.config import settings
from models.database import Base, BillingSubscription, BillingSubscriptionItem, User
from scripts import reconcile_stripe_subscriptions as reconciler


class StripeObjectWithoutGet:
    """Small StripeObject v15 stand-in which deliberately has no ``get`` method."""

    def __init__(self, **values):
        self._values = values

    def __getitem__(self, key):
        return self._values[key]


def stripe_object(**values) -> StripeObjectWithoutGet:
    return StripeObjectWithoutGet(**values)


class RequestBody:
    async def body(self) -> bytes:
        return b'{"test": true}'


class StripeBillingWebhookTests(unittest.IsolatedAsyncioTestCase):
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
                BillingSubscription.__table__,
                BillingSubscriptionItem.__table__,
            ],
        )
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self._reset_user()

    def tearDown(self) -> None:
        self.engine.dispose()

    def _reset_user(
        self,
        *,
        plan: str = "fiel",
        customer_id: str | None = "cus_42",
        subscription_id: str | None = "sub_42",
        billing_status: str | None = None,
    ) -> None:
        with self.session_factory() as db:
            db.query(User).delete()
            db.add(
                User(
                    id=42,
                    email="reader@example.com",
                    name="Reader",
                    password_hash="unused-in-webhook-test",
                    plan=plan,
                    is_active=True,
                    billing_customer_id=customer_id,
                    billing_subscription_id=subscription_id,
                    billing_status=billing_status,
                    email_verified=True,
                )
            )
            db.commit()

    def _subscription(
        self,
        *,
        status: str = "active",
        top_level_period: bool = True,
        subscription_id: str = "sub_42",
        customer_id: str = "cus_42",
        plan: str = "catequista",
        price_id: str = "price_catequista",
        created: int = 1_700_000_000,
    ) -> StripeObjectWithoutGet:
        values = dict(
            id=subscription_id,
            customer=customer_id,
            status=status,
            metadata=stripe_object(user_id="42", plan=plan),
            items=stripe_object(
                data=[
                    stripe_object(
                        price=stripe_object(id=price_id),
                        current_period_end=1_800_000_000,
                    )
                ]
            ),
            cancel_at_period_end=False,
            created=created,
        )
        if top_level_period:
            values["current_period_end"] = 1_800_000_000
        return stripe_object(**values)

    async def _dispatch(
        self,
        event: StripeObjectWithoutGet,
        *,
        retrieved_subscription: StripeObjectWithoutGet | None = None,
        subscriptions_by_id: dict[str, StripeObjectWithoutGet | Exception] | None = None,
        listed_subscriptions: list[StripeObjectWithoutGet] | None = None,
    ) -> Mock:
        webhook_service = SimpleNamespace(construct_event=Mock(return_value=event))

        def retrieve_subscription(subscription_id: str):
            if subscriptions_by_id is not None and subscription_id in subscriptions_by_id:
                value = subscriptions_by_id[subscription_id]
                if isinstance(value, Exception):
                    raise value
                return value
            return retrieved_subscription or self._subscription()

        subscription_service = SimpleNamespace(
            retrieve=Mock(side_effect=retrieve_subscription),
            list=Mock(return_value=stripe_object(data=listed_subscriptions or [])),
        )
        customer_service = SimpleNamespace(list=Mock(return_value=stripe_object(data=[])))
        with (
            patch.object(settings, "stripe_webhook_secret", "whsec_test"),
            patch.object(settings, "stripe_price_catequista", "price_catequista"),
            patch.object(settings, "stripe_price_apologeta", "price_apologeta"),
            patch.object(billing, "_configure_stripe"),
            patch.object(billing, "SessionLocal", self.session_factory),
            patch.object(billing.stripe, "Webhook", webhook_service, create=True),
            patch.object(billing.stripe, "Subscription", subscription_service, create=True),
            patch.object(billing.stripe, "Customer", customer_service, create=True),
        ):
            result = await billing.stripe_webhook(
                RequestBody(),
                stripe_signature="test-signature",
            )

        self.assertEqual(result, {"received": True})
        webhook_service.construct_event.assert_called_once_with(
            payload=b'{"test": true}',
            sig_header="test-signature",
            secret="whsec_test",
        )
        return subscription_service.retrieve

    def _user(self) -> User:
        with self.session_factory() as db:
            return db.get(User, 42)

    async def test_checkout_session_completed_accepts_objects_without_get(self) -> None:
        event = stripe_object(
            id="evt_checkout",
            type="checkout.session.completed",
            data=stripe_object(
                object=stripe_object(
                    id="cs_42",
                    payment_status="paid",
                    client_reference_id="42",
                    customer="cus_42",
                    subscription="sub_42",
                    metadata=stripe_object(user_id="42", plan="catequista"),
                )
            ),
        )

        with patch.object(
            billing,
            "lock_user_for_billing_mutation",
            wraps=billing.lock_user_for_billing_mutation,
        ) as user_lock, patch.object(
            billing,
            "run_in_threadpool",
            wraps=billing.run_in_threadpool,
        ) as threadpool:
            retrieve = await self._dispatch(event, retrieved_subscription=self._subscription())

        user = self._user()
        self.assertEqual(user.plan, "catequista")
        self.assertEqual(user.billing_provider, "stripe")
        self.assertEqual(user.billing_status, "active")
        self.assertEqual(user.billing_customer_id, "cus_42")
        self.assertEqual(user.billing_subscription_id, "sub_42")
        retrieve.assert_called_once_with("sub_42")
        user_lock.assert_called_once()
        self.assertEqual(user_lock.call_args.args[1], 42)
        threadpool.assert_awaited_once()
        self.assertIs(
            threadpool.await_args.args[0],
            billing._process_stripe_webhook_payload,
        )
        self.assertEqual(threadpool.await_args.args[1], b'{"test": true}')

    async def test_async_payment_success_replaces_prior_failed_checkout_projection(self) -> None:
        with self.session_factory() as db:
            db.add(
                BillingSubscription(
                    user_id=42,
                    provider="stripe",
                    provider_status="checkout_failed",
                    entitlement_state="inactive",
                    external_subscription_id="cs_async_retry",
                    provider_customer_id="cus_42",
                )
            )
            db.commit()
        event = stripe_object(
            id="evt_async_success_after_failure",
            type="checkout.session.async_payment_succeeded",
            data=stripe_object(
                object=stripe_object(
                    id="cs_async_retry",
                    payment_status="paid",
                    client_reference_id="42",
                    customer="cus_42",
                    subscription="sub_42",
                    metadata=stripe_object(user_id="42", plan="catequista"),
                )
            ),
        )

        await self._dispatch(event, retrieved_subscription=self._subscription())

        with self.session_factory() as db:
            checkout = db.query(BillingSubscription).filter_by(
                external_subscription_id="cs_async_retry"
            ).one()
            active = db.query(BillingSubscription).filter_by(
                external_subscription_id="sub_42"
            ).one()
            user = db.get(User, 42)
            self.assertEqual(checkout.provider_status, "checkout_complete")
            self.assertEqual(checkout.entitlement_state, "inactive")
            self.assertEqual(active.entitlement_state, "entitled")
            self.assertEqual(user.plan, "catequista")

    async def test_async_payment_failure_after_completed_event_marks_checkout_terminal(self) -> None:
        with self.session_factory() as db:
            db.add(
                BillingSubscription(
                    user_id=42,
                    provider="stripe",
                    provider_status="checkout_pending",
                    entitlement_state="pending",
                    external_subscription_id="cs_async_failure",
                    provider_customer_id="cus_42",
                )
            )
            db.commit()

        def event(event_id: str, event_type: str, payment_status: str):
            return stripe_object(
                id=event_id,
                type=event_type,
                data=stripe_object(
                    object=stripe_object(
                        id="cs_async_failure",
                        payment_status=payment_status,
                        client_reference_id="42",
                        customer="cus_42",
                        subscription="sub_42",
                        metadata=stripe_object(user_id="42", plan="catequista"),
                    )
                ),
            )

        incomplete = self._subscription(status="incomplete")
        await self._dispatch(
            event("evt_async_initial", "checkout.session.completed", "unpaid"),
            retrieved_subscription=incomplete,
        )
        with self.session_factory() as db:
            self.assertEqual(
                db.query(BillingSubscription).filter_by(
                    external_subscription_id="cs_async_failure"
                ).one().provider_status,
                "checkout_complete",
            )

        await self._dispatch(
            event("evt_async_failed", "checkout.session.async_payment_failed", "unpaid"),
            retrieved_subscription=incomplete,
        )
        with self.session_factory() as db:
            checkout = db.query(BillingSubscription).filter_by(
                external_subscription_id="cs_async_failure"
            ).one()
            self.assertEqual(checkout.provider_status, "checkout_failed")
            self.assertEqual(checkout.entitlement_state, "inactive")

    async def test_first_activation_notifies_owner_by_email(self) -> None:
        event = stripe_object(
            id="evt_first_activation",
            type="checkout.session.completed",
            data=stripe_object(
                object=stripe_object(
                    id="cs_first_activation",
                    payment_status="paid",
                    client_reference_id="42",
                    customer="cus_42",
                    subscription="sub_42",
                    metadata=stripe_object(user_id="42", plan="catequista"),
                )
            ),
        )

        with (
            patch.object(settings, "owner_email", "owner@example.com"),
            patch.object(billing, "send_email", return_value=True) as notify,
        ):
            await self._dispatch(event, retrieved_subscription=self._subscription())

        notify.assert_called_once()
        args, _ = notify.call_args
        self.assertEqual(args[0], "owner@example.com")
        self.assertIn("Catequista", args[1])

    async def test_renewal_does_not_renotify_owner(self) -> None:
        self._reset_user(billing_status="active")
        event = stripe_object(
            id="evt_renewal",
            type="invoice.paid",
            data=stripe_object(
                object=stripe_object(
                    id="in_renewal",
                    status="paid",
                    customer="cus_42",
                    parent=stripe_object(
                        subscription_details=stripe_object(subscription="sub_42")
                    ),
                )
            ),
        )

        with (
            patch.object(settings, "owner_email", "owner@example.com"),
            patch.object(billing, "send_email", return_value=True) as notify,
        ):
            await self._dispatch(event, retrieved_subscription=self._subscription())

        notify.assert_not_called()

    async def test_subscription_created_activates_plan_from_current_stripe_state(self) -> None:
        event = stripe_object(
            id="evt_subscription",
            type="customer.subscription.created",
            data=stripe_object(object=self._subscription()),
        )

        retrieve = await self._dispatch(event)

        user = self._user()
        self.assertEqual(user.plan, "catequista")
        self.assertEqual(user.billing_status, "active")
        retrieve.assert_called_once_with("sub_42")

    async def test_invoice_payment_succeeded_uses_new_parent_subscription_schema(self) -> None:
        event = stripe_object(
            id="evt_invoice_succeeded",
            type="invoice.payment_succeeded",
            data=stripe_object(
                object=stripe_object(
                    id="in_42",
                    status="paid",
                    customer="cus_42",
                    parent=stripe_object(
                        subscription_details=stripe_object(subscription="sub_42")
                    ),
                )
            ),
        )

        retrieve = await self._dispatch(event, retrieved_subscription=self._subscription())

        user = self._user()
        self.assertEqual(user.plan, "catequista")
        self.assertEqual(user.billing_status, "active")
        retrieve.assert_called_once_with("sub_42")

    async def test_invoice_paid_also_reconciles_subscription(self) -> None:
        event = stripe_object(
            id="evt_invoice_paid",
            type="invoice.paid",
            data=stripe_object(
                object=stripe_object(
                    id="in_42",
                    status="paid",
                    customer="cus_42",
                    parent=stripe_object(
                        subscription_details=stripe_object(subscription="sub_42")
                    ),
                )
            ),
        )

        retrieve = await self._dispatch(event, retrieved_subscription=self._subscription())

        user = self._user()
        self.assertEqual(user.plan, "catequista")
        self.assertEqual(user.billing_status, "active")
        retrieve.assert_called_once_with("sub_42")

    async def test_period_end_is_read_from_subscription_item_in_new_schema(self) -> None:
        event = stripe_object(
            id="evt_new_period_schema",
            type="checkout.session.completed",
            data=stripe_object(
                object=stripe_object(
                    id="cs_period",
                    payment_status="paid",
                    client_reference_id="42",
                    customer="cus_42",
                    subscription="sub_42",
                    metadata=stripe_object(user_id="42", plan="catequista"),
                )
            ),
        )

        await self._dispatch(
            event,
            retrieved_subscription=self._subscription(top_level_period=False),
        )

        self.assertIsNotNone(self._user().billing_current_period_end)

    async def test_replaying_same_event_is_idempotent(self) -> None:
        event = stripe_object(
            id="evt_replayed",
            type="checkout.session.completed",
            data=stripe_object(
                object=stripe_object(
                    id="cs_42",
                    payment_status="paid",
                    client_reference_id="42",
                    customer="cus_42",
                    subscription="sub_42",
                    metadata=stripe_object(user_id="42", plan="catequista"),
                )
            ),
        )

        await self._dispatch(event, retrieved_subscription=self._subscription())
        first_state = (
            self._user().plan,
            self._user().billing_customer_id,
            self._user().billing_subscription_id,
            self._user().billing_status,
            self._user().billing_current_period_end,
        )
        await self._dispatch(event, retrieved_subscription=self._subscription())
        second_state = (
            self._user().plan,
            self._user().billing_customer_id,
            self._user().billing_subscription_id,
            self._user().billing_status,
            self._user().billing_current_period_end,
        )

        self.assertEqual(second_state, first_state)

    async def test_all_nine_supported_events_are_idempotent_and_return_2xx(self) -> None:
        supported = (
            billing.CHECKOUT_WEBHOOK_EVENTS
            | billing.SUBSCRIPTION_WEBHOOK_EVENTS
            | billing.INVOICE_WEBHOOK_EVENTS
        )
        self.assertEqual(len(supported), 9)

        for event_type in sorted(supported):
            with self.subTest(event_type=event_type):
                self._reset_user()
                if event_type == "checkout.session.async_payment_failed":
                    subscription_status = "incomplete"
                elif event_type == "customer.subscription.deleted":
                    subscription_status = "canceled"
                elif event_type == "invoice.payment_failed":
                    subscription_status = "past_due"
                else:
                    subscription_status = "active"
                subscription = self._subscription(status=subscription_status)

                if event_type in billing.CHECKOUT_WEBHOOK_EVENTS:
                    data = stripe_object(
                        id=f"cs_{event_type.rsplit('.', 1)[-1]}",
                        payment_status="paid" if subscription_status == "active" else "unpaid",
                        client_reference_id="42",
                        customer="cus_42",
                        subscription="sub_42",
                        metadata=stripe_object(user_id="42", plan="catequista"),
                    )
                elif event_type in billing.SUBSCRIPTION_WEBHOOK_EVENTS:
                    data = subscription
                else:
                    data = stripe_object(
                        id=f"in_{event_type.rsplit('.', 1)[-1]}",
                        status="paid" if subscription_status == "active" else "open",
                        customer="cus_42",
                        parent=stripe_object(
                            subscription_details=stripe_object(subscription="sub_42")
                        ),
                    )

                event = stripe_object(
                    id=f"evt_{event_type.replace('.', '_')}",
                    type=event_type,
                    data=stripe_object(object=data),
                )
                await self._dispatch(event, retrieved_subscription=subscription)
                first_state = (
                    self._user().plan,
                    self._user().billing_customer_id,
                    self._user().billing_subscription_id,
                    self._user().billing_status,
                    self._user().billing_current_period_end,
                    self._user().billing_cancel_at_period_end,
                )
                await self._dispatch(event, retrieved_subscription=subscription)
                second_state = (
                    self._user().plan,
                    self._user().billing_customer_id,
                    self._user().billing_subscription_id,
                    self._user().billing_status,
                    self._user().billing_current_period_end,
                    self._user().billing_cancel_at_period_end,
                )
                self.assertEqual(second_state, first_state)

    async def test_unmatched_old_event_is_acknowledged_instead_of_staying_pending(self) -> None:
        event = stripe_object(
            id="evt_old_unmatched",
            type="checkout.session.completed",
            data=stripe_object(
                object=stripe_object(
                    id="cs_old_unmatched",
                    payment_status="paid",
                    client_reference_id="999",
                    customer="cus_unknown",
                    subscription="sub_unknown",
                    metadata=stripe_object(user_id="999", plan="catequista"),
                )
            ),
        )

        retrieve = await self._dispatch(event)

        retrieve.assert_not_called()
        self.assertEqual(self._user().plan, "fiel")

    async def test_async_failure_without_subscription_is_acknowledged_and_links_customer(self) -> None:
        self._reset_user(customer_id=None, subscription_id=None)
        event = stripe_object(
            id="evt_async_failed_without_subscription",
            type="checkout.session.async_payment_failed",
            data=stripe_object(
                object=stripe_object(
                    id="cs_async_failed",
                    payment_status="unpaid",
                    client_reference_id="42",
                    customer="cus_recovered",
                    subscription=None,
                    metadata=stripe_object(user_id="42", plan="catequista"),
                )
            ),
        )

        retrieve = await self._dispatch(event)

        retrieve.assert_not_called()
        user = self._user()
        self.assertEqual(user.plan, "fiel")
        self.assertEqual(user.billing_provider, "stripe")
        self.assertEqual(user.billing_customer_id, "cus_recovered")

    async def test_transient_stripe_failure_remains_retryable(self) -> None:
        event = stripe_object(
            id="evt_transient_failure",
            type="checkout.session.completed",
            data=stripe_object(
                object=stripe_object(
                    id="cs_transient_failure",
                    payment_status="paid",
                    client_reference_id="42",
                    customer="cus_42",
                    subscription="sub_42",
                    metadata=stripe_object(user_id="42", plan="catequista"),
                )
            ),
        )

        with self.assertRaises(HTTPException) as raised:
            await self._dispatch(
                event,
                subscriptions_by_id={
                    "sub_42": billing.stripe.error.APIConnectionError("temporary outage")
                },
            )

        self.assertEqual(raised.exception.status_code, 500)
        self.assertEqual(self._user().plan, "fiel")

    async def test_late_deleted_event_does_not_downgrade_newer_active_subscription(self) -> None:
        self._reset_user(
            plan="apologeta",
            subscription_id="sub_new",
            billing_status="active",
        )
        old_subscription = self._subscription(
            subscription_id="sub_old",
            status="canceled",
            created=100,
        )
        new_subscription = self._subscription(
            subscription_id="sub_new",
            plan="apologeta",
            price_id="price_apologeta",
            status="active",
            created=200,
        )
        event = stripe_object(
            id="evt_old_deleted_late",
            type="customer.subscription.deleted",
            data=stripe_object(object=old_subscription),
        )

        await self._dispatch(
            event,
            subscriptions_by_id={
                "sub_old": old_subscription,
                "sub_new": new_subscription,
            },
            listed_subscriptions=[new_subscription, old_subscription],
        )

        user = self._user()
        self.assertEqual(user.plan, "apologeta")
        self.assertEqual(user.billing_status, "active")
        self.assertEqual(user.billing_subscription_id, "sub_new")

    async def test_newer_active_subscription_wins_when_events_arrive_out_of_order(self) -> None:
        self._reset_user(
            plan="catequista",
            subscription_id="sub_old",
            billing_status="active",
        )
        old_subscription = self._subscription(
            subscription_id="sub_old",
            status="active",
            created=100,
        )
        new_subscription = self._subscription(
            subscription_id="sub_new",
            plan="apologeta",
            price_id="price_apologeta",
            status="active",
            created=200,
        )
        event = stripe_object(
            id="evt_new_created_first",
            type="customer.subscription.created",
            data=stripe_object(object=new_subscription),
        )

        await self._dispatch(
            event,
            subscriptions_by_id={
                "sub_old": old_subscription,
                "sub_new": new_subscription,
            },
            listed_subscriptions=[new_subscription, old_subscription],
        )

        user = self._user()
        self.assertEqual(user.plan, "apologeta")
        self.assertEqual(user.billing_status, "active")
        self.assertEqual(user.billing_subscription_id, "sub_new")

    async def test_non_active_subscription_never_unlocks_paid_plan(self) -> None:
        event = stripe_object(
            id="evt_incomplete",
            type="checkout.session.completed",
            data=stripe_object(
                object=stripe_object(
                    id="cs_incomplete",
                    payment_status="unpaid",
                    client_reference_id="42",
                    customer="cus_42",
                    subscription="sub_42",
                    metadata=stripe_object(user_id="42", plan="catequista"),
                )
            ),
        )

        await self._dispatch(event, retrieved_subscription=self._subscription(status="incomplete"))

        user = self._user()
        self.assertEqual(user.plan, "fiel")
        self.assertEqual(user.billing_status, "incomplete")

    async def test_unknown_price_never_unlocks_plan_from_metadata_alone(self) -> None:
        subscription = stripe_object(
            id="sub_42",
            customer="cus_42",
            status="active",
            metadata=stripe_object(user_id="42", plan="catequista"),
            items=stripe_object(
                data=[
                    stripe_object(
                        price=stripe_object(id="price_not_configured"),
                        current_period_end=1_800_000_000,
                    )
                ]
            ),
            cancel_at_period_end=False,
        )
        event = stripe_object(
            id="evt_unknown_price",
            type="checkout.session.completed",
            data=stripe_object(
                object=stripe_object(
                    id="cs_unknown_price",
                    payment_status="paid",
                    client_reference_id="42",
                    customer="cus_42",
                    subscription="sub_42",
                    metadata=stripe_object(user_id="42", plan="catequista"),
                )
            ),
        )

        await self._dispatch(event, retrieved_subscription=subscription)

        user = self._user()
        self.assertEqual(user.plan, "fiel")
        self.assertEqual(user.billing_status, "active")

    def test_authenticated_sync_activates_confirmed_subscription(self) -> None:
        response = Response()
        with (
            patch.object(billing, "_configure_stripe"),
            patch.object(settings, "stripe_price_catequista", "price_catequista"),
            patch.object(billing, "SessionLocal", self.session_factory),
            patch.object(
                billing,
                "lock_user_for_billing_mutation",
                wraps=billing.lock_user_for_billing_mutation,
            ) as user_lock,
            patch.object(
                billing,
                "_latest_subscription_for_user",
                return_value=self._subscription(top_level_period=False),
            ),
        ):
            result = billing.sync_billing_subscription(response, current_user=self._user())

        self.assertTrue(result.synced)
        self.assertEqual(result.plan, "catequista")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._user().billing_status, "active")
        user_lock.assert_called_once()
        self.assertEqual(user_lock.call_args.args[1], 42)

    def test_authenticated_sync_returns_accepted_while_stripe_is_pending(self) -> None:
        response = Response()
        with (
            patch.object(billing, "_configure_stripe"),
            patch.object(billing, "SessionLocal", self.session_factory),
            patch.object(billing, "_latest_subscription_for_user", return_value=None),
        ):
            result = billing.sync_billing_subscription(response, current_user=self._user())

        self.assertFalse(result.synced)
        self.assertEqual(result.plan, "fiel")
        self.assertEqual(response.status_code, 202)

    def test_periodic_reconciler_applies_once_then_is_idempotent(self) -> None:
        subscription = self._subscription(top_level_period=False)
        with (
            patch.object(settings, "billing_provider", "stripe"),
            patch.object(settings, "stripe_secret_key", "sk_test_local_only"),
            patch.object(settings, "stripe_price_catequista", "price_catequista"),
            patch.object(reconciler, "SessionLocal", self.session_factory),
            patch.object(
                reconciler,
                "_latest_subscription_for_user",
                return_value=subscription,
            ),
        ):
            first = reconciler.run(apply=True)
            second = reconciler.run(apply=True)

        self.assertEqual(first["checked"], 1)
        self.assertEqual(first["changed"], 1)
        self.assertEqual(first["errors"], [])
        self.assertEqual(second["checked"], 1)
        self.assertEqual(second["unchanged"], 1)
        self.assertEqual(second["errors"], [])
        self.assertEqual(self._user().plan, "catequista")
        self.assertEqual(self._user().billing_status, "active")


if __name__ == "__main__":
    unittest.main()
