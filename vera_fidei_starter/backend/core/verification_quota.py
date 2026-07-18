from __future__ import annotations

import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func

from core.config import settings
from core.plans import is_owner_email, verification_limit_for_plan
from models.database import User, VerificationHistory
from schemas.citation import VerificationUsage


def _usage_timezone() -> datetime.tzinfo:
    try:
        return ZoneInfo(settings.usage_reset_timezone)
    except ZoneInfoNotFoundError:
        return datetime.timezone.utc


def _month_bounds() -> tuple[datetime.datetime, datetime.datetime, datetime.datetime]:
    tz = _usage_timezone()
    now = datetime.datetime.now(tz)
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if period_start.month == 12:
        resets_at = period_start.replace(year=period_start.year + 1, month=1)
    else:
        resets_at = period_start.replace(month=period_start.month + 1)
    return now, period_start, resets_at


def _to_db_utc(value: datetime.datetime) -> datetime.datetime:
    return value.astimezone(datetime.timezone.utc).replace(tzinfo=None)


def _threshold(limit: int | None, used: int) -> tuple[float, str | None, bool]:
    if limit is None:
        return 0.0, None, False
    if limit <= 0:
        return 100.0, "full", True
    percent_used = min(100.0, round((used / limit) * 100, 1))
    blocked = used >= limit
    if blocked:
        return percent_used, "full", True
    if percent_used >= 90:
        return percent_used, "almost", False
    if percent_used >= 50:
        return percent_used, "half", False
    return percent_used, None, False


def _message(threshold: str | None, limit: int | None, used: int, remaining: int | None) -> str | None:
    if limit is None:
        return "Seu plano tem verificações ilimitadas."
    if threshold == "full":
        return "Limite mensal de verificações atingido."
    if threshold == "almost":
        return f"Você já usou 90% das verificações do mês. Restam {remaining}."
    if threshold == "half":
        return f"Você já usou metade das verificações do mês. Restam {remaining}."
    return None


def get_verification_usage(db, user: User) -> VerificationUsage:
    now, period_start, resets_at = _month_bounds()
    plan = user.plan or "fiel"
    limit = None if is_owner_email(user.email) else verification_limit_for_plan(plan)
    used = (
        db.query(func.count(VerificationHistory.id))
        .filter(
            VerificationHistory.user_id == user.id,
            VerificationHistory.created_at >= _to_db_utc(period_start),
            VerificationHistory.created_at < _to_db_utc(resets_at),
        )
        .scalar()
        or 0
    )
    remaining = None if limit is None else max(limit - used, 0)
    percent_used, threshold, blocked = _threshold(limit, used)
    return VerificationUsage(
        plan=plan,
        limit=limit,
        used=used,
        remaining=remaining,
        period_start=period_start,
        resets_at=resets_at,
        reset_seconds=max(0, int((resets_at - now).total_seconds())),
        percent_used=percent_used,
        threshold=threshold,
        message=_message(threshold, limit, used, remaining),
        blocked=blocked,
    )
