from __future__ import annotations

import datetime
import hashlib
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException, Response
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.routes import auth
from core import deps, security
from models.database import Base, EmailVerificationToken, PasswordResetToken, User
from schemas.auth import (
    ContactRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
)


class BrowserSessionCookieTests(unittest.TestCase):
    def test_web_login_sets_http_only_cookie_without_returning_token(self) -> None:
        response = Response()
        with (
            patch.object(auth, "login", return_value=TokenResponse(access_token="secret.jwt")),
            patch.object(auth.settings, "vera_environment", "production"),
        ):
            result = auth.web_login(
                LoginRequest(email="owner@example.com", password="secret1"),
                response,
            )

        cookie = response.headers["set-cookie"]
        self.assertEqual(result, {"authenticated": True})
        self.assertIn("vf_token=secret.jwt", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("Secure", cookie)
        self.assertIn("SameSite=lax", cookie)
        self.assertNotIn("secret.jwt", str(result))

    def test_cookie_authentication_and_bearer_compatibility(self) -> None:
        user = SimpleNamespace(id=7, email="reader@example.com")
        with (
            patch.object(deps, "decode_token", return_value={"sub": "7"}) as decode,
            patch.object(deps, "_get_user_by_id", return_value=user),
        ):
            self.assertIs(deps.get_current_user("", "browser-cookie"), user)
            decode.assert_called_once_with("browser-cookie")

        with (
            patch.object(deps, "decode_token", return_value={"sub": "7"}) as decode,
            patch.object(deps, "_get_user_by_id", return_value=user),
        ):
            self.assertIs(deps.get_current_user("Bearer native-token", "browser-cookie"), user)
            decode.assert_called_once_with("native-token")

    def test_malformed_authorization_header_is_rejected(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            deps.get_current_user("Basic abc", "browser-cookie")
        self.assertEqual(raised.exception.status_code, 401)

    def test_session_version_revokes_old_tokens_but_accepts_legacy_tokens_at_version_zero(self) -> None:
        legacy_user = SimpleNamespace(id=7, email="reader@example.com", session_version=0)
        with (
            patch.object(deps, "decode_token", return_value={"sub": "7"}),
            patch.object(deps, "_get_user_by_id", return_value=legacy_user),
        ):
            self.assertIs(deps.get_current_user("Bearer legacy-token", None), legacy_user)

        reset_user = SimpleNamespace(id=7, email="reader@example.com", session_version=1)
        with (
            patch.object(deps, "decode_token", return_value={"sub": "7", "sv": 0}),
            patch.object(deps, "_get_user_by_id", return_value=reset_user),
            self.assertRaises(HTTPException) as revoked,
        ):
            deps.get_current_user("Bearer old-token", None)
        self.assertEqual(revoked.exception.status_code, 401)
        self.assertIn("revogada", revoked.exception.detail)

        with (
            patch.object(deps, "decode_token", return_value={"sub": "7", "sv": 1}),
            patch.object(deps, "_get_user_by_id", return_value=reset_user),
        ):
            self.assertIs(deps.get_current_user("Bearer new-token", None), reset_user)

    def test_new_tokens_carry_the_current_session_version(self) -> None:
        with patch.object(security.jwt, "encode", return_value="signed.jwt") as encode:
            self.assertEqual(security.create_access_token(7, session_version=4), "signed.jwt")

        payload = encode.call_args.args[0]
        self.assertEqual(payload["sub"], "7")
        self.assertEqual(payload["sv"], 4)
        self.assertIn("exp", payload)


class AccountRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(
            self.engine,
            tables=[User.__table__, PasswordResetToken.__table__, EmailVerificationToken.__table__],
        )
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.session_factory() as db:
            db.add(
                User(
                    id=1,
                    email="reader@example.com",
                    name="Reader",
                    password_hash="old-hash",
                    plan="fiel",
                    is_active=True,
                )
            )
            db.commit()

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_recovery_is_generic_hashed_expiring_and_single_use(self) -> None:
        raw_token = "known-reset-token-with-enough-length"
        with (
            patch.object(auth, "SessionLocal", self.session_factory),
            patch.object(auth.secrets, "token_urlsafe", return_value=raw_token),
            patch.object(auth, "send_email") as send_email,
        ):
            result = auth.forgot_password(ForgotPasswordRequest(email="reader@example.com"))

        self.assertIn("Se o e-mail estiver cadastrado", result["message"])
        send_email.assert_called_once()
        with self.session_factory() as db:
            stored = db.query(PasswordResetToken).one()
            self.assertEqual(stored.token_hash, hashlib.sha256(raw_token.encode()).hexdigest())
            self.assertNotEqual(stored.token_hash, raw_token)
            self.assertGreater(stored.expires_at, datetime.datetime.utcnow())

        with (
            patch.object(auth, "SessionLocal", self.session_factory),
            patch.object(auth, "hash_password", return_value="new-hash"),
        ):
            auth.reset_password(ResetPasswordRequest(token=raw_token, password="new-secret"))
            with self.assertRaises(HTTPException) as raised:
                auth.reset_password(ResetPasswordRequest(token=raw_token, password="new-secret"))

        self.assertEqual(raised.exception.status_code, 400)
        with self.session_factory() as db:
            self.assertEqual(db.get(User, 1).password_hash, "new-hash")
            self.assertEqual(db.get(User, 1).session_version, 1)
            self.assertTrue(db.query(PasswordResetToken).one().used)

    def test_unknown_email_has_same_public_response_and_sends_nothing(self) -> None:
        with (
            patch.object(auth, "SessionLocal", self.session_factory),
            patch.object(auth, "send_email") as send_email,
        ):
            result = auth.forgot_password(ForgotPasswordRequest(email="missing@example.com"))

        self.assertIn("Se o e-mail estiver cadastrado", result["message"])
        send_email.assert_not_called()
        with self.session_factory() as db:
            self.assertEqual(db.query(PasswordResetToken).count(), 0)

    def test_password_reset_delivery_failure_is_logged_without_account_enumeration(self) -> None:
        with (
            patch.object(auth, "SessionLocal", self.session_factory),
            patch.object(auth, "send_email", return_value=False),
            self.assertLogs(auth.logger.name, level="WARNING") as captured,
        ):
            result = auth.forgot_password(ForgotPasswordRequest(email="reader@example.com"))

        self.assertIn("Se o e-mail estiver cadastrado", result["message"])
        self.assertTrue(any("password_reset_email_not_sent" in line for line in captured.output))

    def test_resend_and_contact_do_not_report_success_when_delivery_fails(self) -> None:
        current_user = SimpleNamespace(id=1, email_verified=False)
        with (
            patch.object(auth, "_send_verification_email", return_value=False),
            self.assertRaises(HTTPException) as resend_error,
        ):
            auth.resend_verification(current_user)
        self.assertEqual(resend_error.exception.status_code, 503)

        contact = ContactRequest(
            name="Reader",
            email="reader@example.com",
            subject="Ajuda com a conta",
            message="Preciso de ajuda para acessar minha conta.",
        )
        with (
            patch.object(auth, "send_email", return_value=False),
            self.assertLogs(auth.logger.name, level="WARNING") as captured,
            self.assertRaises(HTTPException) as contact_error,
        ):
            auth.contact(contact)
        self.assertEqual(contact_error.exception.status_code, 503)
        self.assertTrue(any("contact_email_not_sent" in line for line in captured.output))

    def test_new_passwords_require_at_least_eight_characters(self) -> None:
        with self.assertRaises(ValidationError):
            RegisterRequest(name="Reader", email="reader@example.com", password="1234567")
        with self.assertRaises(ValidationError):
            ResetPasswordRequest(token="valid-reset-token", password="1234567")

        self.assertEqual(
            RegisterRequest(name="Reader", email="reader@example.com", password="12345678").password,
            "12345678",
        )
        self.assertEqual(
            ResetPasswordRequest(token="valid-reset-token", password="12345678").password,
            "12345678",
        )


if __name__ == "__main__":
    unittest.main()
