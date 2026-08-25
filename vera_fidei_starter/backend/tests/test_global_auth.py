from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core import auth, deps
from core.config import settings
from models.database import Base, User


class GlobalAuthenticationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine, tables=[User.__table__])
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.session_factory() as db:
            db.add_all(
                [
                    User(
                        id=7,
                        email="active@example.com",
                        name="Active",
                        password_hash="hash",
                        plan="fiel",
                        is_active=True,
                        session_version=2,
                    ),
                    User(
                        id=8,
                        email="inactive@example.com",
                        name="Inactive",
                        password_hash="hash",
                        plan="fiel",
                        is_active=False,
                        session_version=0,
                    ),
                ]
            )
            db.commit()

    def tearDown(self) -> None:
        self.engine.dispose()

    def require(
        self,
        *,
        x_api_key: str = "",
        query_api_key: str = "",
        authorization: str = "",
        cookie: str | None = None,
    ) -> None:
        auth.require_api_key(
            x_api_key=x_api_key,
            api_key=query_api_key,
            authorization=authorization,
            vf_token=cookie,
        )

    def test_configured_header_api_key_remains_accepted(self) -> None:
        with (
            patch.object(settings, "api_key", "server-secret"),
            patch.object(auth, "get_current_user", side_effect=AssertionError("JWT should not be read")),
        ):
            self.require(x_api_key="server-secret", authorization="Bearer malformed")

    def test_legacy_query_api_key_remains_accepted(self) -> None:
        with (
            patch.object(settings, "api_key", "server-secret"),
            patch.object(auth, "get_current_user", side_effect=AssertionError("JWT should not be read")),
        ):
            self.require(x_api_key="wrong", query_api_key="server-secret")

    def test_valid_bearer_session_is_accepted_without_api_key(self) -> None:
        with (
            patch.object(settings, "api_key", "server-secret"),
            patch.object(deps, "decode_token", return_value={"sub": "7", "sv": 2}),
            patch.object(deps, "_get_db", self.session_factory),
        ):
            self.require(authorization="Bearer valid.jwt")

    def test_valid_cookie_session_is_accepted_when_no_api_key_is_configured(self) -> None:
        with (
            patch.object(settings, "api_key", ""),
            patch.object(deps, "decode_token", return_value={"sub": "7", "sv": 2}),
            patch.object(deps, "_get_db", self.session_factory),
        ):
            self.require(cookie="valid.cookie.jwt")

    def test_valid_session_can_replace_an_invalid_api_key(self) -> None:
        with (
            patch.object(settings, "api_key", "server-secret"),
            patch.object(deps, "decode_token", return_value={"sub": "7", "sv": 2}),
            patch.object(deps, "_get_db", self.session_factory),
        ):
            self.require(x_api_key="wrong", authorization="Bearer valid.jwt")

    def test_missing_credentials_are_rejected_even_without_a_configured_api_key(self) -> None:
        with (
            patch.object(settings, "api_key", ""),
            self.assertRaises(HTTPException) as raised,
        ):
            self.require()
        self.assertEqual(raised.exception.status_code, 401)

    def test_direct_dependency_call_with_fastapi_defaults_is_also_rejected(self) -> None:
        with (
            patch.object(settings, "api_key", ""),
            self.assertRaises(HTTPException) as raised,
        ):
            auth.require_api_key()
        self.assertEqual(raised.exception.status_code, 401)

    def test_invalid_api_key_and_invalid_jwt_are_rejected(self) -> None:
        with (
            patch.object(settings, "api_key", "server-secret"),
            patch.object(
                deps,
                "decode_token",
                side_effect=HTTPException(status_code=401, detail="Token inválido ou expirado."),
            ),
            self.assertRaises(HTTPException) as raised,
        ):
            self.require(x_api_key="wrong", authorization="Bearer invalid.jwt")
        self.assertEqual(raised.exception.status_code, 401)

    def test_inactive_user_session_is_rejected(self) -> None:
        with (
            patch.object(settings, "api_key", "server-secret"),
            patch.object(deps, "decode_token", return_value={"sub": "8", "sv": 0}),
            patch.object(deps, "_get_db", self.session_factory),
            self.assertRaises(HTTPException) as raised,
        ):
            self.require(authorization="Bearer inactive.jwt")
        self.assertEqual(raised.exception.status_code, 401)

    def test_revoked_session_version_is_rejected(self) -> None:
        with (
            patch.object(settings, "api_key", "server-secret"),
            patch.object(deps, "decode_token", return_value={"sub": "7", "sv": 1}),
            patch.object(deps, "_get_db", self.session_factory),
            self.assertRaises(HTTPException) as raised,
        ):
            self.require(authorization="Bearer revoked.jwt")
        self.assertEqual(raised.exception.status_code, 401)
        self.assertIn("revogada", raised.exception.detail)


if __name__ == "__main__":
    unittest.main()
