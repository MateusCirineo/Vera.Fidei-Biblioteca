from __future__ import annotations

import datetime as dt
import os
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from app.services.dispatcher import PipelineDispatcher
from app.social.ledger import SocialLedger
from app.social.package import style_is_approved
from core.config import settings


def _backend_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return Path(__file__).resolve().parents[2] / path


def publication_readiness() -> dict[str, bool | str]:
    font_ok = Path(settings.social_body_font_path).is_file()
    checks: dict[str, bool | str] = {
        "style_approved": style_is_approved(),
        "publish_enabled": settings.instagram_publish_enabled,
        "schedule_enabled": settings.instagram_schedule_enabled,
        "credentials_rotated": bool(settings.instagram_credentials_rotated_at.strip()),
        "one_time_legacy_override": settings.instagram_allow_exposed_credentials_once,
        "instagram_credentials_present": bool(
            settings.instagram_access_token.strip()
            and settings.instagram_business_account_id.strip()
        ),
        "public_upload_configured": bool(
            settings.deploy_ssh_host.strip()
            and (settings.deploy_ssh_key_path.strip() or settings.deploy_ssh_password.strip())
        ),
        "font_available": font_ok,
        "timezone": settings.instagram_schedule_timezone,
    }
    checks["ready"] = all(
        value is True
        for key, value in checks.items()
        if key not in {"timezone", "ready", "one_time_legacy_override"}
    )
    return checks


def run_scheduled_post() -> dict[str, Any]:
    """Executa no máximo uma publicação por data local, com trava em arquivo."""
    ready = publication_readiness()
    if not ready["ready"]:
        return {"status": "blocked", "readiness": ready}

    now = dt.datetime.now(ZoneInfo(settings.instagram_schedule_timezone))
    local_date = now.date().isoformat()
    ledger = SocialLedger(_backend_path(settings.social_ledger_path))
    if any(
        event.get("event") == "scheduled_published"
        and event.get("local_date") == local_date
        for event in ledger.events()
    ):
        return {"status": "already_published_today", "local_date": local_date}

    lock = ledger.path.parent / f"schedule-{local_date}.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return {"status": "already_running", "local_date": local_date}
    try:
        os.write(descriptor, f"pid={os.getpid()}\nstarted={now.isoformat()}\n".encode("utf-8"))
    finally:
        os.close(descriptor)

    try:
        ctx = PipelineDispatcher().run(
            "Gerar e publicar carrossel rastreável no Instagram do Vera.Fidei",
            initial_findings={
                "social_options": {
                    "day": now.timetuple().tm_yday,
                    "publish_requested": True,
                    "scheduled_date": local_date,
                }
            },
        )
        publish_data = ctx.reports.get("social_publish_agent") or {}
        remote_id = str(publish_data.get("remote_media_id") or "")
        statuses = [
            {"agent": result.agent_name, "status": result.status, "warnings": result.warnings}
            for result in ctx.history
        ]
        if not remote_id:
            ledger.append(
                {
                    "event": "scheduled_failed",
                    "local_date": local_date,
                    "execution_id": ctx.execution_id,
                    "statuses": statuses,
                }
            )
            lock.unlink(missing_ok=True)
            return {
                "status": "blocked",
                "local_date": local_date,
                "execution_id": ctx.execution_id,
                "agents": statuses,
            }
        ledger.append(
            {
                "event": "scheduled_published",
                "local_date": local_date,
                "execution_id": ctx.execution_id,
                "remote_media_id": remote_id,
            }
        )
        return {
            "status": "published",
            "local_date": local_date,
            "execution_id": ctx.execution_id,
            "remote_media_id": remote_id,
            "agents": statuses,
        }
    except Exception as exc:
        ledger.append(
            {
                "event": "scheduled_failed",
                "local_date": local_date,
                "error_type": type(exc).__name__,
            }
        )
        lock.unlink(missing_ok=True)
        return {"status": "error", "local_date": local_date, "error": type(exc).__name__}
