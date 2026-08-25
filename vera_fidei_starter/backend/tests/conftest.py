"""Test configuration — stub heavy runtime dependencies missing in unit-test env.

This conftest is loaded automatically by pytest before any test file.
It installs minimal fake modules for packages that require a running server
or are not installed in the unit-test venv (PyJWT, stripe, sendgrid,
passlib). The real `core` package is left untouched since it lives in the
backend directory and is importable as-is once the stubs are in place.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock


def _stub(name: str, **attrs) -> types.ModuleType:
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules.setdefault(name, mod)
    return sys.modules[name]


# ── jose (JWT) ─────────────────────────────────────────────────────────────────
_jwt = _stub("jwt", InvalidTokenError=Exception)
_jwt.decode = MagicMock(return_value={})
_jwt.encode = MagicMock(return_value="stub.token")

# ── stripe ─────────────────────────────────────────────────────────────────────
# Keep the fallback usable by exception-path tests when stripe-python is not
# installed in the lightweight unit-test environment.
class _StripeError(Exception):
    pass


class _InvalidRequestError(_StripeError):
    pass


class _APIConnectionError(_StripeError):
    pass


class _SignatureVerificationError(_StripeError):
    pass


_stub(
    "stripe",
    error=types.SimpleNamespace(
        StripeError=_StripeError,
        InvalidRequestError=_InvalidRequestError,
        APIConnectionError=_APIConnectionError,
        SignatureVerificationError=_SignatureVerificationError,
    ),
)

# ── sendgrid ───────────────────────────────────────────────────────────────────
_sg = _stub("sendgrid")
_sg_helpers = _stub("sendgrid.helpers")
_sg_mail = _stub("sendgrid.helpers.mail",
                 Mail=MagicMock, To=MagicMock, From=MagicMock,
                 Subject=MagicMock, Content=MagicMock)

# ── passlib ────────────────────────────────────────────────────────────────────
_stub("passlib")
_stub("passlib.context", CryptContext=MagicMock)

# ── boto3 / botocore (optional cloud storage) ──────────────────────────────────
_stub("boto3")
_stub("botocore")
_stub("botocore.exceptions", ClientError=Exception)
