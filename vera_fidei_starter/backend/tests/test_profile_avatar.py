from __future__ import annotations

import datetime
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from api.routes import auth
from models.database import Base, User


PNG = b"\x89PNG\r\n\x1a\nprofile-photo"
JPEG = b"\xff\xd8\xffprofile-photo"
WEBP = b"RIFF\x10\x00\x00\x00WEBPprofile-photo"


def avatar_request(
    body: bytes,
    content_type: str = "image/png",
    *,
    content_length: str | None = None,
    include_content_length: bool = True,
) -> Request:
    headers = [(b"content-type", content_type.encode("ascii"))]
    if include_content_length:
        headers.append(
            (
                b"content-length",
                (content_length if content_length is not None else str(len(body))).encode("ascii"),
            )
        )
    delivered = False

    async def receive():
        nonlocal delivered
        if delivered:
            return {"type": "http.request", "body": b"", "more_body": False}
        delivered = True
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "PUT",
            "scheme": "https",
            "path": "/api/auth/avatar",
            "raw_path": b"/api/auth/avatar",
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 443),
        },
        receive,
    )


class AvatarPayloadValidationTests(unittest.TestCase):
    def test_accepts_supported_mime_types_with_matching_signatures(self) -> None:
        cases = (
            (PNG, "image/png", "image/png"),
            (JPEG, "image/jpeg; charset=binary", "image/jpeg"),
            (WEBP, "IMAGE/WEBP", "image/webp"),
        )
        for payload, declared_type, expected in cases:
            with self.subTest(content_type=declared_type):
                self.assertEqual(
                    auth._validate_avatar_payload(payload, declared_type),
                    expected,
                )

    def test_rejects_missing_or_unsupported_mime_type(self) -> None:
        for content_type in (None, "", "image/gif", "text/plain"):
            with self.subTest(content_type=content_type), self.assertRaises(HTTPException) as raised:
                auth._validate_avatar_payload(PNG, content_type)
            self.assertEqual(raised.exception.status_code, 415)

    def test_rejects_empty_payload(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            auth._validate_avatar_payload(b"", "image/png")
        self.assertEqual(raised.exception.status_code, 422)

    def test_rejects_payload_over_700_kb(self) -> None:
        payload = b"\x89PNG\r\n\x1a\n" + b"x" * auth.AVATAR_MAX_BYTES
        self.assertGreater(len(payload), auth.AVATAR_MAX_BYTES)
        with self.assertRaises(HTTPException) as raised:
            auth._validate_avatar_payload(payload, "image/png")
        self.assertEqual(raised.exception.status_code, 413)

    def test_rejects_spoofed_or_mismatched_file_signature(self) -> None:
        cases = (
            (JPEG, "image/png"),
            (PNG, "image/jpeg"),
            (b"RIFF\x10\x00\x00\x00NOPEprofile-photo", "image/webp"),
        )
        for payload, content_type in cases:
            with self.subTest(content_type=content_type), self.assertRaises(HTTPException) as raised:
                auth._validate_avatar_payload(payload, content_type)
            self.assertEqual(raised.exception.status_code, 422)


class ProfileAvatarEndpointTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine, tables=[User.__table__])
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.session_factory() as db:
            db.add(
                User(
                    id=74,
                    email="avatar@example.com",
                    name="Avatar Reader",
                    password_hash="stored-password-hash",
                    plan="fiel",
                    is_active=True,
                    email_verified=True,
                )
            )
            db.commit()
        self.current_user = SimpleNamespace(id=74)

    def tearDown(self) -> None:
        self.engine.dispose()

    async def test_upload_get_and_delete_avatar(self) -> None:
        with patch.object(auth, "SessionLocal", self.session_factory):
            uploaded = await auth.update_profile_avatar(
                avatar_request(PNG),
                self.current_user,
            )

            self.assertRegex(uploaded["avatar_url"], r"^/api/auth/avatar\?v=\d+$")
            served = auth.profile_avatar(self.current_user)
            self.assertEqual(served.body, PNG)
            self.assertEqual(served.media_type, "image/png")
            self.assertEqual(served.headers["cache-control"], "private, max-age=3600")
            self.assertEqual(served.headers["content-security-policy"], "default-src 'none'")
            self.assertEqual(served.headers["x-content-type-options"], "nosniff")

            self.assertEqual(auth.delete_profile_avatar(self.current_user), {"removed": True})
            with self.assertRaises(HTTPException) as missing:
                auth.profile_avatar(self.current_user)
            self.assertEqual(missing.exception.status_code, 404)

        with self.session_factory() as db:
            user = db.get(User, 74)
            self.assertIsNone(user.avatar_data)
            self.assertIsNone(user.avatar_content_type)
            self.assertIsNone(user.avatar_updated_at)

    async def test_upload_short_circuits_invalid_declared_length(self) -> None:
        with (
            patch.object(auth, "SessionLocal", self.session_factory),
            self.assertRaises(HTTPException) as raised,
        ):
            await auth.update_profile_avatar(
                avatar_request(PNG, content_length=str(auth.AVATAR_MAX_BYTES + 1)),
                self.current_user,
            )
        self.assertEqual(raised.exception.status_code, 413)

        with (
            patch.object(auth, "SessionLocal", self.session_factory),
            self.assertRaises(HTTPException) as malformed,
        ):
            await auth.update_profile_avatar(
                avatar_request(PNG, content_length="not-a-number"),
                self.current_user,
            )
        self.assertEqual(malformed.exception.status_code, 400)

    async def test_upload_limits_chunked_body_without_content_length(self) -> None:
        oversized = b"\x89PNG\r\n\x1a\n" + b"x" * auth.AVATAR_MAX_BYTES
        with (
            patch.object(auth, "SessionLocal", self.session_factory),
            self.assertRaises(HTTPException) as raised,
        ):
            await auth.update_profile_avatar(
                avatar_request(oversized, include_content_length=False),
                self.current_user,
            )
        self.assertEqual(raised.exception.status_code, 413)

    async def test_upload_requires_existing_account(self) -> None:
        with (
            patch.object(auth, "SessionLocal", self.session_factory),
            self.assertRaises(HTTPException) as raised,
        ):
            await auth.update_profile_avatar(
                avatar_request(PNG),
                SimpleNamespace(id=999),
            )
        self.assertEqual(raised.exception.status_code, 404)

    def test_user_schema_exposes_versioned_url_but_not_avatar_bytes(self) -> None:
        with self.session_factory() as db:
            user = db.get(User, 74)
            user.avatar_data = b"PRIVATE-AVATAR-BYTES"
            user.avatar_content_type = "image/png"
            user.avatar_updated_at = datetime.datetime(2026, 8, 28, 3, 2, 1)
            db.commit()

            response = auth.me(user).model_dump()

        self.assertEqual(response["avatar_url"], "/api/auth/avatar?v=1787886121000000")
        self.assertNotIn("avatar_data", response)
        self.assertNotIn("avatar_content_type", response)
        self.assertNotIn("avatar_updated_at", response)
        self.assertNotIn("PRIVATE-AVATAR-BYTES", repr(response))


if __name__ == "__main__":
    unittest.main()
