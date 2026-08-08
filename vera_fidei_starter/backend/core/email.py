from __future__ import annotations

import json
import logging
import urllib.request

from core.config import settings

_log = logging.getLogger(__name__)


def send_email(to: str, subject: str, html: str) -> bool:
    if not settings.resend_api_key:
        _log.warning("RESEND_API_KEY not configured — email not sent to %s", to)
        return False
    try:
        payload = json.dumps({
            "from": settings.email_from,
            "to": [to],
            "subject": subject,
            "html": html,
        }).encode()
        req = urllib.request.Request(
            "https://api.resend.com/emails",
            data=payload,
            headers={
                "Authorization": f"Bearer {settings.resend_api_key}",
                "Content-Type": "application/json",
                "User-Agent": "VeraFidei/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = resp.status
        if status == 200:
            return True
        _log.warning("Resend returned status %s for %s", status, to)
        return False
    except Exception as exc:
        _log.warning("Resend email failed to %s: %s", to, exc)
        return False
