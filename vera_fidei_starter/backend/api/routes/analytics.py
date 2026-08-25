from __future__ import annotations

import datetime
import hashlib
import hmac
import re
import secrets
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_

from core.config import settings
from core.deps import require_owner
from core.plans import PLAN_LABELS, normalize_email
from models.database import (
    SearchUsage,
    SessionLocal,
    SitePageView,
    SiteVisitor,
    User,
    VerificationHistory,
)

router = APIRouter()

VISITOR_COOKIE = "vf_visitor"
VISITOR_COOKIE_MAX_AGE = 365 * 24 * 60 * 60
ONLINE_WINDOW_MINUTES = 5
ANALYTICS_TIMEZONE = ZoneInfo("America/Sao_Paulo")
PAID_PLANS = {"catequista", "apologeta", "patristico", "magisterio"}
ACTIVE_BILLING_STATUSES = {"active", "trialing"}
_BOT_PATTERN = re.compile(
    r"bot|crawler|spider|slurp|headless|lighthouse|preview|uptime|monitoring|curl|wget",
    re.IGNORECASE,
)
_PATH_PATTERN = re.compile(r"^/[A-Za-z0-9_./%\-]*$")


class AnalyticsEventRequest(BaseModel):
    path: str = Field(..., min_length=1, max_length=255)
    event: Literal["view", "heartbeat"] = "view"


class MetricPeriod(BaseModel):
    today: int
    last_7_days: int
    last_30_days: int


class MetricCount(BaseModel):
    key: str
    label: str
    count: int


class RecentAccount(BaseModel):
    id: int
    name: str
    email: str
    plan: str
    plan_label: str
    billing_status: str | None
    email_verified: bool
    is_active: bool
    created_at: datetime.datetime


class DailyActivity(BaseModel):
    date: datetime.date
    visitors: int
    page_views: int
    registrations: int


class AdminMetricsResponse(BaseModel):
    generated_at: datetime.datetime
    refresh_after_seconds: int = 15
    tracking_started_at: datetime.datetime | None
    accounts_total: int
    accounts_active: int
    accounts_disabled: int
    accounts_free: int
    subscribers_active: int
    subscribers_canceling: int
    subscriptions_pending: int
    conversion_rate: float
    registrations: MetricPeriod
    visitors_unique_total: int
    visitors_online_now: int
    visitors: MetricPeriod
    page_views: MetricPeriod
    searches_today: int
    verifications_today: int
    plans: list[MetricCount]
    subscription_statuses: list[MetricCount]
    top_pages_7_days: list[MetricCount]
    daily_activity: list[DailyActivity]
    recent_accounts: list[RecentAccount]


def _cookie_secret() -> bytes:
    secret = (settings.jwt_secret or settings.api_key or "vera-fidei").encode("utf-8")
    return secret


def _new_visitor_cookie() -> str:
    token = secrets.token_urlsafe(24)
    signature = hmac.new(_cookie_secret(), token.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{token}.{signature}"


def _valid_visitor_token(cookie_value: str | None) -> str | None:
    if not cookie_value or "." not in cookie_value:
        return None
    token, signature = cookie_value.rsplit(".", 1)
    if not token or len(token) > 64 or len(signature) != 64:
        return None
    expected = hmac.new(_cookie_secret(), token.encode("utf-8"), hashlib.sha256).hexdigest()
    return token if hmac.compare_digest(signature, expected) else None


def _visitor_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _clean_path(value: str) -> str:
    path = value.split("?", 1)[0].split("#", 1)[0].strip()
    if not _PATH_PATTERN.fullmatch(path) or path.startswith("/api/"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Rota inválida.")
    return path.rstrip("/") or "/"


def _is_bot(request: Request) -> bool:
    return bool(_BOT_PATTERN.search(request.headers.get("user-agent", "")))


@router.post("/event", status_code=status.HTTP_202_ACCEPTED)
def record_event(
    payload: AnalyticsEventRequest,
    request: Request,
    response: Response,
    vf_visitor: str | None = Cookie(default=None),
) -> None:
    """Record privacy-preserving first-party activity from a real browser."""

    if _is_bot(request):
        return
    path = _clean_path(payload.path)
    if path == "/admin" or path.startswith("/admin/"):
        return

    token = _valid_visitor_token(vf_visitor)
    if token is None:
        cookie_value = _new_visitor_cookie()
        token = _valid_visitor_token(cookie_value)
        assert token is not None
        response.set_cookie(
            VISITOR_COOKIE,
            cookie_value,
            max_age=VISITOR_COOKIE_MAX_AGE,
            httponly=True,
            secure=settings.vera_environment.strip().lower() in {"production", "prod"},
            samesite="lax",
            path="/",
        )

    now = datetime.datetime.utcnow()
    digest = _visitor_hash(token)
    with SessionLocal() as db:
        visitor = db.query(SiteVisitor).filter(SiteVisitor.visitor_hash == digest).first()
        if visitor is None:
            visitor = SiteVisitor(
                visitor_hash=digest,
                first_seen_at=now,
                last_seen_at=now,
                view_count=0,
                last_path=path,
            )
            db.add(visitor)
            db.flush()

        visitor.last_seen_at = now
        visitor.last_path = path
        if payload.event == "view":
            last_viewed_at = (
                db.query(func.max(SitePageView.viewed_at))
                .filter(SitePageView.visitor_id == visitor.id)
                .scalar()
            )
            if last_viewed_at is None or (now - last_viewed_at).total_seconds() >= 2:
                visitor.view_count = int(visitor.view_count or 0) + 1
                db.add(SitePageView(visitor_id=visitor.id, path=path, viewed_at=now))
        db.commit()


def _period_count(db, model, column, *, today_start, week_start, month_start, filters=()) -> MetricPeriod:
    query = db.query(func.count()).select_from(model).filter(*filters)
    return MetricPeriod(
        today=int(query.filter(column >= today_start).scalar() or 0),
        last_7_days=int(query.filter(column >= week_start).scalar() or 0),
        last_30_days=int(query.filter(column >= month_start).scalar() or 0),
    )


def _as_utc_aware(value: datetime.datetime) -> datetime.datetime:
    """Treat database-naive timestamps as UTC and return an explicit UTC instant."""

    if value.tzinfo is None:
        return value.replace(tzinfo=datetime.timezone.utc)
    return value.astimezone(datetime.timezone.utc)


def _as_db_utc(value: datetime.datetime) -> datetime.datetime:
    """Return the naive UTC representation used by the existing DateTime columns."""

    return _as_utc_aware(value).replace(tzinfo=None)


def _local_midnight_as_db_utc(day: datetime.date) -> datetime.datetime:
    local_midnight = datetime.datetime.combine(day, datetime.time.min, tzinfo=ANALYTICS_TIMEZONE)
    return _as_db_utc(local_midnight)


def _build_admin_metrics(db, *, now: datetime.datetime | None = None) -> AdminMetricsResponse:
    now_utc = _as_utc_aware(now or datetime.datetime.now(datetime.timezone.utc))
    now_db = _as_db_utc(now_utc)
    local_today = now_utc.astimezone(ANALYTICS_TIMEZONE).date()
    today_start = _local_midnight_as_db_utc(local_today)
    week_start = _local_midnight_as_db_utc(local_today - datetime.timedelta(days=6))
    month_start = _local_midnight_as_db_utc(local_today - datetime.timedelta(days=29))
    online_start = now_db - datetime.timedelta(minutes=ONLINE_WINDOW_MINUTES)
    owner_email = normalize_email(settings.owner_email)
    non_owner = func.lower(User.email) != owner_email
    active_subscription = and_(
        User.plan.in_(PAID_PLANS),
        User.billing_status.in_(ACTIVE_BILLING_STATUSES),
    )

    accounts_total = int(db.query(func.count(User.id)).filter(non_owner).scalar() or 0)
    accounts_active = int(
        db.query(func.count(User.id)).filter(non_owner, User.is_active.is_(True)).scalar() or 0
    )
    accounts_disabled = accounts_total - accounts_active
    accounts_free = int(
        db.query(func.count(User.id)).filter(non_owner, User.plan == "fiel").scalar() or 0
    )
    subscribers_active = int(
        db.query(func.count(User.id)).filter(non_owner, active_subscription).scalar() or 0
    )
    subscribers_canceling = int(
        db.query(func.count(User.id))
        .filter(non_owner, active_subscription, User.billing_cancel_at_period_end.is_(True))
        .scalar()
        or 0
    )
    subscriptions_pending = int(
        db.query(func.count(User.id))
        .filter(
            non_owner,
            or_(
                User.billing_status.in_({"pending_payment", "incomplete", "past_due"}),
                User.billing_status.is_(None) & User.plan.in_(PAID_PLANS),
            ),
        )
        .scalar()
        or 0
    )

    registrations = _period_count(
        db,
        User,
        User.created_at,
        today_start=today_start,
        week_start=week_start,
        month_start=month_start,
        filters=(non_owner,),
    )
    visitors = _period_count(
        db,
        SiteVisitor,
        SiteVisitor.last_seen_at,
        today_start=today_start,
        week_start=week_start,
        month_start=month_start,
    )
    page_views = _period_count(
        db,
        SitePageView,
        SitePageView.viewed_at,
        today_start=today_start,
        week_start=week_start,
        month_start=month_start,
    )

    visitors_unique_total = int(db.query(func.count(SiteVisitor.id)).scalar() or 0)
    visitors_online_now = int(
        db.query(func.count(SiteVisitor.id))
        .filter(SiteVisitor.last_seen_at >= online_start)
        .scalar()
        or 0
    )
    tracking_started_at = db.query(func.min(SiteVisitor.first_seen_at)).scalar()
    searches_today = int(
        db.query(func.coalesce(func.sum(SearchUsage.count), 0))
        .filter(SearchUsage.usage_date == local_today)
        .scalar()
        or 0
    )
    verifications_today = int(
        db.query(func.count(VerificationHistory.id))
        .filter(VerificationHistory.created_at >= today_start)
        .scalar()
        or 0
    )

    plan_rows = (
        db.query(User.plan, func.count(User.id))
        .filter(non_owner)
        .group_by(User.plan)
        .order_by(func.count(User.id).desc())
        .all()
    )
    plans = [
        MetricCount(
            key=plan or "fiel",
            label=PLAN_LABELS.get(plan or "fiel", (plan or "Fiel").title()),
            count=int(count),
        )
        for plan, count in plan_rows
    ]

    status_labels = {
        "active": "Ativa",
        "trialing": "Em teste",
        "pending_payment": "Pagamento pendente",
        "past_due": "Pagamento atrasado",
        "incomplete": "Incompleta",
        "canceled": "Cancelada",
        "unpaid": "Não paga",
        "none": "Sem assinatura",
    }
    status_key = func.coalesce(User.billing_status, "none")
    status_rows = (
        db.query(status_key.label("status"), func.count(User.id))
        .filter(non_owner)
        .group_by(status_key)
        .order_by(func.count(User.id).desc())
        .all()
    )
    subscription_statuses = [
        MetricCount(key=key, label=status_labels.get(key, key.replace("_", " ").title()), count=int(count))
        for key, count in status_rows
    ]

    top_page_rows = (
        db.query(SitePageView.path, func.count(SitePageView.id).label("views"))
        .filter(SitePageView.viewed_at >= week_start)
        .group_by(SitePageView.path)
        .order_by(func.count(SitePageView.id).desc())
        .limit(10)
        .all()
    )
    top_pages = [MetricCount(key=path, label=path, count=int(count)) for path, count in top_page_rows]

    daily_activity: list[DailyActivity] = []
    for offset in range(7):
        local_day = local_today - datetime.timedelta(days=6 - offset)
        day_start = _local_midnight_as_db_utc(local_day)
        day_end = _local_midnight_as_db_utc(local_day + datetime.timedelta(days=1))
        daily_activity.append(
            DailyActivity(
                date=local_day,
                visitors=int(
                    db.query(func.count(func.distinct(SitePageView.visitor_id)))
                    .filter(SitePageView.viewed_at >= day_start, SitePageView.viewed_at < day_end)
                    .scalar()
                    or 0
                ),
                page_views=int(
                    db.query(func.count(SitePageView.id))
                    .filter(SitePageView.viewed_at >= day_start, SitePageView.viewed_at < day_end)
                    .scalar()
                    or 0
                ),
                registrations=int(
                    db.query(func.count(User.id))
                    .filter(non_owner, User.created_at >= day_start, User.created_at < day_end)
                    .scalar()
                    or 0
                ),
            )
        )

    recent_rows = (
        db.query(User)
        .filter(non_owner)
        .order_by(User.created_at.desc(), User.id.desc())
        .limit(10)
        .all()
    )
    recent_accounts = [
        RecentAccount(
            id=user.id,
            name=user.name,
            email=user.email,
            plan=user.plan or "fiel",
            plan_label=PLAN_LABELS.get(user.plan or "fiel", (user.plan or "Fiel").title()),
            billing_status=user.billing_status,
            email_verified=bool(user.email_verified),
            is_active=bool(user.is_active),
            created_at=_as_utc_aware(user.created_at),
        )
        for user in recent_rows
    ]

    return AdminMetricsResponse(
        generated_at=now_utc,
        tracking_started_at=_as_utc_aware(tracking_started_at) if tracking_started_at else None,
        accounts_total=accounts_total,
        accounts_active=accounts_active,
        accounts_disabled=accounts_disabled,
        accounts_free=accounts_free,
        subscribers_active=subscribers_active,
        subscribers_canceling=subscribers_canceling,
        subscriptions_pending=subscriptions_pending,
        conversion_rate=round((subscribers_active / accounts_total * 100) if accounts_total else 0, 2),
        registrations=registrations,
        visitors_unique_total=visitors_unique_total,
        visitors_online_now=visitors_online_now,
        visitors=visitors,
        page_views=page_views,
        searches_today=searches_today,
        verifications_today=verifications_today,
        plans=plans,
        subscription_statuses=subscription_statuses,
        top_pages_7_days=top_pages,
        daily_activity=daily_activity,
        recent_accounts=recent_accounts,
    )


@router.get("/admin/metrics", response_model=AdminMetricsResponse)
def admin_metrics(
    response: Response,
    _owner: User = Depends(require_owner),
) -> AdminMetricsResponse:
    response.headers["Cache-Control"] = "private, no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    with SessionLocal() as db:
        return _build_admin_metrics(db)
