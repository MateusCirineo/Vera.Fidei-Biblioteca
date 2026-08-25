from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import HTTPException

from api.routes import billing, books
from core.config import settings, validate_runtime_security
from core.deps import require_owner


class OwnerAuthorizationTests(unittest.TestCase):
    def test_configured_owner_is_allowed(self) -> None:
        user = SimpleNamespace(email=settings.owner_email)
        self.assertIs(require_owner(user), user)

    def test_other_user_is_forbidden(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            require_owner(SimpleNamespace(email="outro@example.com"))
        self.assertEqual(raised.exception.status_code, 403)

    def test_every_book_mutation_requires_owner(self) -> None:
        expected = {
            ("", "POST"),
            ("/ingest-auto", "POST"),
            ("/{book_id}", "DELETE"),
            ("/{book_id}/files/{file_id}/metadata", "PATCH"),
            ("/{book_id}/ingest-pdf", "POST"),
        }
        protected: set[tuple[str, str]] = set()
        for route in books.router.routes:
            dependency_calls = {dependency.call for dependency in route.dependant.dependencies}
            if require_owner not in dependency_calls:
                continue
            for method in route.methods or set():
                protected.add((route.path, method))
        self.assertTrue(expected.issubset(protected))


class CouponAdministrationTests(unittest.TestCase):
    def test_non_owner_cannot_create_coupon(self) -> None:
        payload = billing.AdminCouponCreateRequest(code="TESTE20", percent_off=20)
        with self.assertRaises(HTTPException) as raised:
            billing.create_admin_coupon(payload, SimpleNamespace(email="outro@example.com"))
        self.assertEqual(raised.exception.status_code, 403)

    def test_owner_can_create_coupon(self) -> None:
        payload = billing.AdminCouponCreateRequest(
            code="teste20",
            percent_off=20,
            duration="once",
            max_redemptions=10,
        )
        promotion = {
            "id": "promo_test",
            "code": "TESTE20",
            "active": True,
            "times_redeemed": 0,
            "max_redemptions": 10,
            "created": 1_700_000_000,
            "promotion": {
                "coupon": {
                    "id": "coupon_test",
                    "percent_off": 20,
                    "duration": "once",
                }
            },
        }
        promotion_service = SimpleNamespace(
            list=Mock(return_value={"data": []}),
            create=Mock(return_value=promotion),
        )
        coupon_service = SimpleNamespace(create=Mock(return_value={"id": "coupon_test"}))
        with (
            patch.object(billing, "_configure_stripe"),
            patch.object(billing.stripe, "PromotionCode", promotion_service, create=True),
            patch.object(billing.stripe, "Coupon", coupon_service, create=True),
        ):
            result = billing.create_admin_coupon(
                payload,
                SimpleNamespace(email=settings.owner_email),
            )

        self.assertEqual(result.code, "TESTE20")
        self.assertEqual(result.percent_off, 20)
        coupon_service.create.assert_called_once()
        self.assertEqual(promotion_service.create.call_args.kwargs["code"], "TESTE20")
        self.assertEqual(promotion_service.create.call_args.kwargs["max_redemptions"], 10)


class RuntimeSecurityTests(unittest.TestCase):
    def test_production_rejects_default_jwt_secret(self) -> None:
        with (
            patch.object(settings, "vera_environment", "production"),
            patch.object(settings, "jwt_secret", "CHANGE_ME_IN_PRODUCTION"),
        ):
            with self.assertRaises(RuntimeError):
                validate_runtime_security()

    def test_production_accepts_strong_jwt_secret(self) -> None:
        with (
            patch.object(settings, "vera_environment", "production"),
            patch.object(settings, "jwt_secret", "x" * 64),
            patch.object(settings, "owner_email", "owner@example.com"),
        ):
            validate_runtime_security()


if __name__ == "__main__":
    unittest.main()
