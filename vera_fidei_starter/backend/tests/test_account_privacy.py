from __future__ import annotations

import datetime
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import stripe

from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.routes import auth, billing
from models.database import (
    ApiKey,
    Base,
    BillingRequest,
    EmailVerificationToken,
    Institution,
    InstitutionMember,
    PasswordResetToken,
    SearchUsage,
    User,
    UserFavorite,
    VerificationHistory,
)
from schemas.auth import DeleteAccountRequest


class StripeObjectWithoutGet:
    """Stripe v15 stand-in which deliberately has no ``get`` method."""

    def __init__(self, **values):
        self._values = values

    def __getitem__(self, key):
        return self._values[key]


def stripe_object(**values) -> StripeObjectWithoutGet:
    return StripeObjectWithoutGet(**values)


class AccountPrivacyTests(unittest.TestCase):
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
                UserFavorite.__table__,
                VerificationHistory.__table__,
                BillingRequest.__table__,
                Institution.__table__,
                InstitutionMember.__table__,
                ApiKey.__table__,
                PasswordResetToken.__table__,
                EmailVerificationToken.__table__,
                SearchUsage.__table__,
            ],
        )
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.session_factory() as db:
            user = User(
                id=41,
                email="reader@example.com",
                name="Reader",
                password_hash="stored-password-hash",
                plan="fiel",
                is_active=True,
                email_verified=True,
            )
            db.add(user)
            db.flush()
            db.add_all(
                [
                    UserFavorite(
                        user_id=user.id,
                        kind="book",
                        item_id="32",
                        title="PG001",
                        href="/biblioteca/32",
                        metadata_json='{"page": 12}',
                    ),
                    VerificationHistory(
                        user_id=user.id,
                        citation_text="Texto enviado pelo titular",
                        attributed_to="Autor",
                        response_json='{"status": "ok"}',
                    ),
                    BillingRequest(
                        user_id=user.id,
                        plan="fiel",
                        amount_cents=1000,
                        status="paid",
                        provider="manual_pix",
                        reference_code="PRIVACY-TEST",
                    ),
                    ApiKey(user_id=user.id, key_hash="secret-hash", label="Minha integração"),
                    PasswordResetToken(
                        user_id=user.id,
                        token_hash="reset-hash",
                        expires_at=datetime.datetime.utcnow() + datetime.timedelta(hours=1),
                    ),
                    EmailVerificationToken(user_id=user.id, token_hash="verification-hash"),
                    SearchUsage(user_id=user.id, usage_date=datetime.date(2026, 8, 21), count=3),
                ]
            )
            institution = Institution(name="Grupo de estudos", admin_user_id=user.id)
            db.add(institution)
            db.flush()
            db.add(InstitutionMember(institution_id=institution.id, user_id=user.id, role="admin"))
            db.commit()

    def tearDown(self) -> None:
        self.engine.dispose()

    @property
    def current_user(self):
        return SimpleNamespace(id=41, email="reader@example.com")

    def test_export_contains_portable_data_but_no_secrets(self) -> None:
        with patch.object(auth, "SessionLocal", self.session_factory):
            response = auth.export_personal_data(self.current_user)

        payload = json.loads(response.body)
        serialized = response.body.decode("utf-8")
        self.assertEqual(payload["format"], "vera-fidei-personal-data-v1")
        self.assertEqual(payload["account"]["email"], "reader@example.com")
        self.assertEqual(payload["favorites"][0]["metadata"], {"page": 12})
        self.assertEqual(payload["citation_verifications"][0]["citation_text"], "Texto enviado pelo titular")
        self.assertEqual(payload["api_keys"][0]["label"], "Minha integração")
        self.assertNotIn("stored-password-hash", serialized)
        self.assertNotIn("secret-hash", serialized)
        self.assertNotIn("reset-hash", serialized)
        self.assertIn("attachment;", response.headers["content-disposition"])
        self.assertEqual(response.headers["cache-control"], "no-store, max-age=0")

    def test_delete_removes_account_and_all_linked_operational_data(self) -> None:
        response = Response()
        payload = DeleteAccountRequest(password="correct-password", confirmation="EXCLUIR")
        with (
            patch.object(auth, "SessionLocal", self.session_factory),
            patch.object(auth, "verify_password", return_value=True),
        ):
            result = auth.delete_account(payload, response, self.current_user)

        self.assertEqual(result["message"], "Conta e dados pessoais excluídos.")
        self.assertIn("vf_token=", response.headers["set-cookie"])
        with self.session_factory() as db:
            self.assertIsNone(db.get(User, 41))
            for model in (
                UserFavorite,
                VerificationHistory,
                BillingRequest,
                Institution,
                InstitutionMember,
                ApiKey,
                PasswordResetToken,
                EmailVerificationToken,
                SearchUsage,
            ):
                self.assertEqual(db.query(model).count(), 0, model.__name__)

    def test_delete_blocks_live_stripe_subscription(self) -> None:
        with self.session_factory() as db:
            user = db.get(User, 41)
            user.billing_provider = "stripe"
            user.billing_status = "active"
            db.commit()

        for live_status in sorted(auth.BLOCKING_STRIPE_SUBSCRIPTION_STATUSES):
            with (
                self.subTest(status=live_status),
                patch.object(auth, "SessionLocal", self.session_factory),
                patch.object(auth, "verify_password", return_value=True),
                patch.object(auth, "_stripe_live_subscription_statuses", return_value={live_status}),
                self.assertRaises(HTTPException) as raised,
            ):
                auth.delete_account(
                    DeleteAccountRequest(password="correct-password", confirmation="EXCLUIR"),
                    Response(),
                    self.current_user,
                )

            self.assertEqual(raised.exception.status_code, 409)
        with self.session_factory() as db:
            self.assertIsNotNone(db.get(User, 41))

    def test_delete_checks_stripe_by_email_when_webhook_never_created_local_link(self) -> None:
        """A failed/delayed webhook must not let a paid Stripe account be orphaned."""
        with (
            patch.object(auth, "SessionLocal", self.session_factory),
            patch.object(auth, "verify_password", return_value=True),
            patch.object(auth.settings, "stripe_secret_key", "sk_test_configured"),
            patch.object(auth, "_stripe_live_subscription_statuses", return_value={"paused"}) as live_check,
            self.assertRaises(HTTPException) as raised,
        ):
            auth.delete_account(
                DeleteAccountRequest(password="correct-password", confirmation="EXCLUIR"),
                Response(),
                self.current_user,
            )

        self.assertEqual(raised.exception.status_code, 409)
        live_check.assert_called_once()
        checked_user = live_check.call_args.args[0]
        self.assertEqual(checked_user.email, "reader@example.com")
        self.assertIsNone(checked_user.billing_customer_id)
        self.assertIsNone(checked_user.billing_subscription_id)
        with self.session_factory() as db:
            self.assertIsNotNone(db.get(User, 41))

    def test_delete_fails_closed_when_stripe_cannot_be_checked(self) -> None:
        with self.session_factory() as db:
            user = db.get(User, 41)
            user.billing_customer_id = "cus_reader"
            db.commit()

        with (
            patch.object(auth, "SessionLocal", self.session_factory),
            patch.object(auth, "verify_password", return_value=True),
            patch.object(auth, "_stripe_live_subscription_statuses", side_effect=RuntimeError("timeout")),
            self.assertLogs(auth.logger.name, level="ERROR") as captured,
            self.assertRaises(HTTPException) as raised,
        ):
            auth.delete_account(
                DeleteAccountRequest(password="correct-password", confirmation="EXCLUIR"),
                Response(),
                self.current_user,
            )

        self.assertEqual(raised.exception.status_code, 503)
        self.assertTrue(any("stripe_account_deletion_check_failed" in line for line in captured.output))
        with self.session_factory() as db:
            self.assertIsNotNone(db.get(User, 41))

    def test_delete_uses_live_stripe_state_instead_of_stale_local_status(self) -> None:
        with self.session_factory() as db:
            user = db.get(User, 41)
            user.billing_provider = "stripe"
            user.billing_customer_id = "cus_reader"
            user.billing_status = "active"
            db.commit()

        response = Response()
        with (
            patch.object(auth, "SessionLocal", self.session_factory),
            patch.object(auth, "verify_password", return_value=True),
            patch.object(auth, "_stripe_live_subscription_statuses", return_value={"canceled"}) as live_check,
        ):
            auth.delete_account(
                DeleteAccountRequest(password="correct-password", confirmation="EXCLUIR"),
                response,
                self.current_user,
            )

        live_check.assert_called_once()
        with self.session_factory() as db:
            self.assertIsNone(db.get(User, 41))

    def test_live_stripe_lookup_supports_objects_without_get_and_searches_all_links(self) -> None:
        user = SimpleNamespace(
            id=41,
            email="Reader@Example.com",
            billing_customer_id="cus_stored",
            billing_subscription_id="sub_stored",
        )
        customer_service = SimpleNamespace(
            list=Mock(
                return_value=stripe_object(
                    data=[
                        stripe_object(
                            id="cus_by_email",
                            email="reader@example.com",
                            metadata=stripe_object(user_id="41"),
                        )
                    ]
                )
            )
        )
        subscription_service = SimpleNamespace(
            retrieve=Mock(return_value=stripe_object(id="sub_stored", status="canceled")),
            list=Mock(
                side_effect=[
                    stripe_object(data=[stripe_object(id="sub_active", status="active")]),
                    stripe_object(data=[stripe_object(id="sub_paused", status="paused")]),
                ]
            ),
        )

        with (
            patch.object(billing, "_configure_stripe"),
            patch.object(stripe, "Customer", customer_service, create=True),
            patch.object(stripe, "Subscription", subscription_service, create=True),
        ):
            statuses = auth._stripe_live_subscription_statuses(user)

        self.assertEqual(statuses, {"canceled", "active", "paused"})
        self.assertEqual(
            {call.kwargs["email"] for call in customer_service.list.call_args_list},
            {"Reader@Example.com", "reader@example.com"},
        )
        subscription_service.retrieve.assert_called_once_with("sub_stored")
        self.assertEqual(
            {call.kwargs["customer"] for call in subscription_service.list.call_args_list},
            {"cus_stored", "cus_by_email"},
        )

    def test_delete_requires_exact_confirmation_and_protects_owner(self) -> None:
        with self.assertRaises(HTTPException) as confirmation_error:
            auth.delete_account(
                DeleteAccountRequest(password="correct-password", confirmation="cancelar"),
                Response(),
                self.current_user,
            )
        self.assertEqual(confirmation_error.exception.status_code, 422)

        with (
            patch.object(auth, "is_owner_email", return_value=True),
            self.assertRaises(HTTPException) as owner_error,
        ):
            auth.delete_account(
                DeleteAccountRequest(password="correct-password", confirmation="EXCLUIR"),
                Response(),
                self.current_user,
            )
        self.assertEqual(owner_error.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
