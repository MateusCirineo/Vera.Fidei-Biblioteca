"""Test configuration — stub heavy runtime dependencies missing in unit-test env.

This conftest is loaded automatically by pytest before any test file.
It installs minimal fake modules for packages that require a running server
or are not installed in the unit-test venv (jose JWT, stripe, sendgrid,
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
_jose = _stub("jose", JWTError=Exception)
_jose_jwt = _stub("jose.jwt")
_jose_jwt.decode = MagicMock(return_value={})
_jose_jwt.encode = MagicMock(return_value="stub.token")
_jose.jwt = _jose_jwt

# ── stripe ─────────────────────────────────────────────────────────────────────
_stub("stripe")

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
