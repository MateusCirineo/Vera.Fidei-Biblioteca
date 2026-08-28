from __future__ import annotations

import datetime
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from api.routes import auth
from core import security
from schemas.auth import MobileWebSessionRequest


class MobileWebSessionTests(unittest.TestCase):
    def test_redirect_allowlist_accepts_only_the_exact_relative_viewer_shape(self) -> None:
        self.assertEqual(
            auth._validate_mobile_redirect("/visualizar/42?page=12"),
            "/visualizar/42?page=12",
        )

        rejected = (
            "https://evil.example/visualizar/42?page=12",
            "//evil.example/visualizar/42?page=12",
            "/viewer/pdf?file=/api/pdfs/42&page=12",
            "/visualizar/0?page=12",
            "/visualizar/42?page=0",
            "/visualizar/42?pagina=12",
            "/visualizar/42?page=12&next=https://evil.example",
            "/visualizar/42?page=12#fragment",
            "/visualizar/%34%32?page=12",
            " /visualizar/42?page=12",
        )
        for redirect in rejected:
            with self.subTest(redirect=redirect), self.assertRaises(HTTPException) as raised:
                auth._validate_mobile_redirect(redirect)
            self.assertEqual(raised.exception.status_code, 422)

    def test_exchange_returns_303_and_short_lived_secure_http_only_cookie(self) -> None:
        user = SimpleNamespace(id=17, session_version=3, plan="apologeta")
        with patch.object(auth, "create_access_token", return_value="temporary.web.jwt") as create_token:
            response = auth.mobile_web_session(
                MobileWebSessionRequest(redirect="/visualizar/91?page=7"),
                user,
            )

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/visualizar/91?page=7")
        self.assertEqual(response.headers["cache-control"], "no-store, max-age=0")
        self.assertEqual(response.headers["referrer-policy"], "no-referrer")
        cookie = response.headers["set-cookie"]
        self.assertIn("vf_token=temporary.web.jwt", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("Secure", cookie)
        self.assertIn("SameSite=lax", cookie)
        self.assertIn("Max-Age=900", cookie)
        self.assertNotIn("temporary.web.jwt", response.body.decode())
        create_token.assert_called_once_with(17, 3, expires_minutes=15)

    def test_account_allowlist_accepts_only_profile_and_plans(self) -> None:
        self.assertEqual(auth._validate_mobile_account_redirect("/perfil"), "/perfil")
        self.assertEqual(auth._validate_mobile_account_redirect("/planos"), "/planos")

        rejected = (
            "/admin",
            "/perfil/",
            "/perfil?next=/admin",
            "/planos?coupon=TESTE",
            "https://verafidei.oialfred.com/perfil",
            "//evil.example/perfil",
            "/visualizar/42?page=1",
            " /perfil",
        )
        for redirect in rejected:
            with self.subTest(redirect=redirect), self.assertRaises(HTTPException) as raised:
                auth._validate_mobile_account_redirect(redirect)
            self.assertEqual(raised.exception.status_code, 422)

    def test_account_exchange_uses_same_short_cookie_without_pdf_plan_gate(self) -> None:
        user = SimpleNamespace(id=23, session_version=4, plan="fiel")
        with patch.object(auth, "create_access_token", return_value="account.web.jwt") as create_token:
            post_response = auth.mobile_account_session(
                MobileWebSessionRequest(redirect="/perfil"),
                user,
            )
            get_response = auth.mobile_account_session_webview("/planos", user)

        self.assertEqual(post_response.status_code, 303)
        self.assertEqual(post_response.headers["location"], "/perfil")
        self.assertEqual(get_response.status_code, 303)
        self.assertEqual(get_response.headers["location"], "/planos")
        for response in (post_response, get_response):
            cookie = response.headers["set-cookie"]
            self.assertIn("HttpOnly", cookie)
            self.assertIn("Secure", cookie)
            self.assertIn("Max-Age=900", cookie)
            self.assertNotIn("account.web.jwt", response.body.decode())
        self.assertEqual(create_token.call_count, 2)
        create_token.assert_any_call(23, 4, expires_minutes=15)

    def test_android_webview_get_bridge_has_the_same_cookie_and_redirect_contract(self) -> None:
        user = SimpleNamespace(id=17, session_version=3, plan="apologeta")
        with patch.object(auth, "create_access_token", return_value="temporary.web.jwt"):
            response = auth.mobile_web_session_webview("/visualizar/91?page=7", user)

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/visualizar/91?page=7")
        self.assertIn("HttpOnly", response.headers["set-cookie"])
        self.assertIn("Secure", response.headers["set-cookie"])
        self.assertNotIn("temporary.web.jwt", response.body.decode())

    def test_mobile_exchange_requires_explicit_bearer_not_a_browser_cookie(self) -> None:
        with self.assertRaises(HTTPException) as missing:
            auth._mobile_bearer_user("")
        self.assertEqual(missing.exception.status_code, 401)

        user = SimpleNamespace(id=17, plan="apologeta")
        with patch.object(auth, "get_current_user", return_value=user) as get_user:
            self.assertIs(auth._mobile_bearer_user("Bearer native.jwt"), user)
        get_user.assert_called_once_with(authorization="Bearer native.jwt", vf_token=None)

    def test_pdf_access_is_available_to_every_authenticated_plan(self) -> None:
        for plan in ("fiel", "catequista", "apologeta", "patristico", "magisterio"):
            user = SimpleNamespace(plan=plan)
            self.assertIs(auth._mobile_pdf_user(user), user)

    def test_custom_access_token_lifetime_is_fifteen_minutes(self) -> None:
        before = datetime.datetime.utcnow()
        with patch.object(security.jwt, "encode", return_value="short.jwt") as encode:
            self.assertEqual(
                security.create_access_token(17, session_version=3, expires_minutes=15),
                "short.jwt",
            )
        after = datetime.datetime.utcnow()
        expires_at = encode.call_args.args[0]["exp"]
        self.assertGreaterEqual(expires_at, before + datetime.timedelta(minutes=15))
        self.assertLessEqual(expires_at, after + datetime.timedelta(minutes=15))


if __name__ == "__main__":
    unittest.main()
