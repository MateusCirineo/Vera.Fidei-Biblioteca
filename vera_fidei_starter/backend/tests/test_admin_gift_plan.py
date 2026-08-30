from __future__ import annotations

import datetime
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.routes import billing
from core.config import settings
from models.database import Base, BillingSubscription, BillingSubscriptionItem, User


class AdminGiftPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.owner = SimpleNamespace(email=settings.owner_email)
        with self.session_factory() as db:
            db.add(
                User(
                    id=7,
                    email="promoter@example.com",
                    name="Divulgador",
                    password_hash="unused",
                    plan="fiel",
                    is_active=True,
                    email_verified=True,
                )
            )
            db.commit()

    def _user(self) -> User:
        with self.session_factory() as db:
            return db.get(User, 7)

    def test_grant_sets_active_paid_plan_with_no_expiry_by_default(self) -> None:
        with patch.object(billing, "SessionLocal", self.session_factory):
            result = billing.grant_manual_plan(
                billing.AdminGrantPlanRequest(email="promoter@example.com", plan="patristico"),
                current_user=self.owner,
            )

        self.assertEqual(result.plan, "patristico")
        self.assertEqual(result.billing_status, "active")
        self.assertIsNone(result.billing_current_period_end)
        user = self._user()
        self.assertEqual(user.plan, "patristico")
        self.assertEqual(user.billing_provider, "legacy_manual")

    def test_grant_with_months_sets_expiry_around_90_days_out(self) -> None:
        with patch.object(billing, "SessionLocal", self.session_factory):
            result = billing.grant_manual_plan(
                billing.AdminGrantPlanRequest(email="promoter@example.com", plan="patristico", months=3),
                current_user=self.owner,
            )

        assert result.billing_current_period_end is not None
        delta = result.billing_current_period_end - datetime.datetime.utcnow()
        self.assertTrue(datetime.timedelta(days=88) < delta < datetime.timedelta(days=91))

    def test_grant_rejects_non_owner(self) -> None:
        with patch.object(billing, "SessionLocal", self.session_factory):
            with self.assertRaises(HTTPException) as raised:
                billing.grant_manual_plan(
                    billing.AdminGrantPlanRequest(email="promoter@example.com", plan="patristico"),
                    current_user=SimpleNamespace(email="promoter@example.com"),
                )
        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(self._user().plan, "fiel")

    def test_grant_rejects_invalid_plan(self) -> None:
        with patch.object(billing, "SessionLocal", self.session_factory):
            with self.assertRaises(HTTPException) as raised:
                billing.grant_manual_plan(
                    billing.AdminGrantPlanRequest(email="promoter@example.com", plan="fiel"),
                    current_user=self.owner,
                )
        self.assertEqual(raised.exception.status_code, 400)

    def test_grant_rejects_unknown_email(self) -> None:
        with patch.object(billing, "SessionLocal", self.session_factory):
            with self.assertRaises(HTTPException) as raised:
                billing.grant_manual_plan(
                    billing.AdminGrantPlanRequest(email="ghost@example.com", plan="patristico"),
                    current_user=self.owner,
                )
        self.assertEqual(raised.exception.status_code, 404)

    def test_revoke_reverts_to_free_plan(self) -> None:
        with patch.object(billing, "SessionLocal", self.session_factory):
            billing.grant_manual_plan(
                billing.AdminGrantPlanRequest(email="promoter@example.com", plan="patristico"),
                current_user=self.owner,
            )
            result = billing.revoke_manual_plan(
                billing.AdminRevokePlanRequest(email="promoter@example.com"),
                current_user=self.owner,
            )

        self.assertEqual(result.plan, "fiel")
        self.assertIsNone(result.billing_status)
        user = self._user()
        self.assertEqual(user.plan, "fiel")
        self.assertIsNone(user.billing_provider)

    def test_revoke_refuses_to_touch_a_real_stripe_subscription(self) -> None:
        with self.session_factory() as db:
            user = db.get(User, 7)
            user.plan = "apologeta"
            user.billing_provider = "stripe"
            user.billing_status = "active"
            db.commit()

        with patch.object(billing, "SessionLocal", self.session_factory):
            with self.assertRaises(HTTPException) as raised:
                billing.revoke_manual_plan(
                    billing.AdminRevokePlanRequest(email="promoter@example.com"),
                    current_user=self.owner,
                )
        self.assertEqual(raised.exception.status_code, 400)
        user = self._user()
        self.assertEqual(user.plan, "apologeta")
        self.assertEqual(user.billing_provider, "stripe")

    def test_grant_is_idempotent_and_reusable_for_a_plan_change(self) -> None:
        with patch.object(billing, "SessionLocal", self.session_factory):
            billing.grant_manual_plan(
                billing.AdminGrantPlanRequest(email="promoter@example.com", plan="catequista"),
                current_user=self.owner,
            )
            billing.grant_manual_plan(
                billing.AdminGrantPlanRequest(email="promoter@example.com", plan="patristico"),
                current_user=self.owner,
            )

        with self.session_factory() as db:
            subscriptions = (
                db.query(BillingSubscription).filter(BillingSubscription.user_id == 7).all()
            )
            self.assertEqual(len(subscriptions), 1)
            items = (
                db.query(BillingSubscriptionItem)
                .filter(BillingSubscriptionItem.billing_subscription_id == subscriptions[0].id)
                .all()
            )
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].plan, "patristico")
        self.assertEqual(self._user().plan, "patristico")


if __name__ == "__main__":
    unittest.main()
