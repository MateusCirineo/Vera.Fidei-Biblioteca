from __future__ import annotations

import datetime
import unittest
from unittest.mock import patch

from fastapi import Request, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.routes import analytics
from core.config import settings
from models.database import (
    Base,
    SearchUsage,
    SitePageView,
    SiteVisitor,
    User,
    VerificationHistory,
)


class AdminAnalyticsTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine, expire_on_commit=False)

    @staticmethod
    def _request(user_agent: str = "Mozilla/5.0") -> Request:
        return Request({
            "type": "http",
            "method": "POST",
            "path": "/analytics/event",
            "headers": [(b"user-agent", user_agent.encode("ascii"))],
        })

    def test_event_uses_signed_http_only_cookie_without_storing_ip_or_user_agent(self) -> None:
        response = Response()
        with patch.object(analytics, "SessionLocal", self.Session):
            analytics.record_event(
                analytics.AnalyticsEventRequest(path="/biblioteca?q=ignored", event="view"),
                self._request(),
                response,
                None,
            )

        cookie_header = response.headers["set-cookie"]
        self.assertIn("vf_visitor=", cookie_header)
        self.assertIn("HttpOnly", cookie_header)
        cookie_value = cookie_header.split("vf_visitor=", 1)[1].split(";", 1)[0]
        self.assertIsNotNone(analytics._valid_visitor_token(cookie_value))

        with self.Session() as db:
            visitor = db.query(SiteVisitor).one()
            page_view = db.query(SitePageView).one()
            self.assertEqual(visitor.view_count, 1)
            self.assertEqual(visitor.last_path, "/biblioteca")
            self.assertEqual(page_view.path, "/biblioteca")
            self.assertFalse(hasattr(visitor, "ip_address"))
            self.assertFalse(hasattr(visitor, "user_agent"))

    def test_heartbeat_updates_presence_without_increasing_page_views(self) -> None:
        cookie_value = analytics._new_visitor_cookie()
        with patch.object(analytics, "SessionLocal", self.Session):
            analytics.record_event(
                analytics.AnalyticsEventRequest(path="/verificador", event="view"),
                self._request(),
                Response(),
                cookie_value,
            )
            analytics.record_event(
                analytics.AnalyticsEventRequest(path="/verificador", event="heartbeat"),
                self._request(),
                Response(),
                cookie_value,
            )

        with self.Session() as db:
            self.assertEqual(db.query(SiteVisitor).one().view_count, 1)
            self.assertEqual(db.query(SitePageView).count(), 1)

    def test_bots_and_admin_page_are_not_counted(self) -> None:
        with patch.object(analytics, "SessionLocal", self.Session):
            analytics.record_event(
                analytics.AnalyticsEventRequest(path="/", event="view"),
                self._request("Googlebot/2.1"),
                Response(),
                None,
            )
            analytics.record_event(
                analytics.AnalyticsEventRequest(path="/admin", event="view"),
                self._request(),
                Response(),
                None,
            )
        with self.Session() as db:
            self.assertEqual(db.query(SiteVisitor).count(), 0)

    def test_owner_metrics_separate_free_accounts_and_active_subscribers(self) -> None:
        now = datetime.datetime(2026, 8, 21, 12, 0, 0)
        with self.Session() as db:
            db.add_all([
                User(
                    email=settings.owner_email,
                    name="Owner",
                    password_hash="hash",
                    plan="magisterio",
                    billing_status="owner",
                    created_at=now,
                    email_verified=True,
                ),
                User(
                    email="free@example.com",
                    name="Conta gratuita",
                    password_hash="hash",
                    plan="fiel",
                    created_at=now - datetime.timedelta(hours=1),
                    email_verified=True,
                ),
                User(
                    email="paid@example.com",
                    name="Assinante",
                    password_hash="hash",
                    plan="patristico",
                    billing_status="active",
                    billing_cancel_at_period_end=True,
                    created_at=now - datetime.timedelta(days=5),
                    email_verified=True,
                ),
            ])
            db.flush()
            paid_user = db.query(User).filter(User.email == "paid@example.com").one()
            visitor = SiteVisitor(
                visitor_hash="a" * 64,
                first_seen_at=now - datetime.timedelta(days=1),
                last_seen_at=now - datetime.timedelta(minutes=1),
                view_count=2,
                last_path="/biblioteca",
            )
            db.add(visitor)
            db.flush()
            db.add_all([
                SitePageView(visitor_id=visitor.id, path="/", viewed_at=now - datetime.timedelta(hours=2)),
                SitePageView(visitor_id=visitor.id, path="/biblioteca", viewed_at=now - datetime.timedelta(minutes=1)),
                SearchUsage(user_id=paid_user.id, usage_date=now.date(), count=3),
                VerificationHistory(
                    user_id=paid_user.id,
                    citation_text="Texto",
                    created_at=now - datetime.timedelta(minutes=2),
                ),
            ])
            db.commit()

            result = analytics._build_admin_metrics(db, now=now)

        self.assertEqual(result.accounts_total, 2)
        self.assertEqual(result.accounts_free, 1)
        self.assertEqual(result.subscribers_active, 1)
        self.assertEqual(result.subscribers_canceling, 1)
        self.assertEqual(result.visitors_unique_total, 1)
        self.assertEqual(result.visitors_online_now, 1)
        self.assertEqual(result.page_views.today, 2)
        self.assertEqual(result.searches_today, 3)
        self.assertEqual(result.verifications_today, 1)
        self.assertEqual(len(result.recent_accounts), 2)
        self.assertNotIn(settings.owner_email, {item.email for item in result.recent_accounts})

    def test_brazilian_today_keeps_21h_brt_events_on_the_same_local_date(self) -> None:
        # 01:30 UTC on Aug 25 is still 22:30 BRT on Aug 24. A UTC-date
        # comparison would incorrectly put the 21:15 BRT event on Aug 25.
        now_utc = datetime.datetime(2026, 8, 25, 1, 30)
        current_local_day = datetime.datetime(2026, 8, 25, 0, 15)  # Aug 24, 21:15 BRT
        previous_local_day = datetime.datetime(2026, 8, 24, 2, 59)  # Aug 23, 23:59 BRT

        with self.Session() as db:
            current_user = User(
                email="current@example.com",
                name="Hoje no Brasil",
                password_hash="hash",
                plan="fiel",
                created_at=current_local_day,
            )
            previous_user = User(
                email="previous@example.com",
                name="Ontem no Brasil",
                password_hash="hash",
                plan="fiel",
                created_at=previous_local_day,
            )
            visitor = SiteVisitor(
                visitor_hash="b" * 64,
                first_seen_at=previous_local_day,
                last_seen_at=current_local_day,
                view_count=2,
                last_path="/biblioteca",
            )
            db.add_all([current_user, previous_user, visitor])
            db.flush()
            db.add_all([
                SitePageView(visitor_id=visitor.id, path="/ontem", viewed_at=previous_local_day),
                SitePageView(visitor_id=visitor.id, path="/hoje", viewed_at=current_local_day),
                SearchUsage(user_id=current_user.id, usage_date=datetime.date(2026, 8, 24), count=4),
                SearchUsage(user_id=previous_user.id, usage_date=datetime.date(2026, 8, 25), count=9),
                VerificationHistory(
                    user_id=current_user.id,
                    citation_text="Hoje",
                    created_at=current_local_day,
                ),
                VerificationHistory(
                    user_id=previous_user.id,
                    citation_text="Ontem",
                    created_at=previous_local_day,
                ),
            ])
            db.commit()

            result = analytics._build_admin_metrics(db, now=now_utc)

        self.assertEqual(result.registrations.today, 1)
        self.assertEqual(result.visitors.today, 1)
        self.assertEqual(result.page_views.today, 1)
        self.assertEqual(result.searches_today, 4)
        self.assertEqual(result.verifications_today, 1)
        self.assertEqual(result.daily_activity[-1].date, datetime.date(2026, 8, 24))
        self.assertEqual(result.daily_activity[-1].page_views, 1)

        serialized = result.model_dump(mode="json")
        self.assertTrue(serialized["generated_at"].endswith("Z"))
        self.assertTrue(serialized["tracking_started_at"].endswith("Z"))
        self.assertTrue(serialized["recent_accounts"][0]["created_at"].endswith("Z"))

    def test_brazilian_midnight_starts_at_03_utc(self) -> None:
        # 00:30 BRT on Aug 25: only timestamps at/after 03:00 UTC belong to today.
        now_utc = datetime.datetime(2026, 8, 25, 3, 30)
        with self.Session() as db:
            visitor = SiteVisitor(
                visitor_hash="c" * 64,
                first_seen_at=datetime.datetime(2026, 8, 25, 2, 59),
                last_seen_at=datetime.datetime(2026, 8, 25, 3, 1),
                view_count=2,
                last_path="/depois-da-meia-noite",
            )
            db.add(visitor)
            db.flush()
            db.add_all([
                SitePageView(
                    visitor_id=visitor.id,
                    path="/antes-da-meia-noite",
                    viewed_at=datetime.datetime(2026, 8, 25, 2, 59),
                ),
                SitePageView(
                    visitor_id=visitor.id,
                    path="/depois-da-meia-noite",
                    viewed_at=datetime.datetime(2026, 8, 25, 3, 1),
                ),
            ])
            db.commit()

            result = analytics._build_admin_metrics(db, now=now_utc)

        self.assertEqual(result.page_views.today, 1)
        self.assertEqual(result.daily_activity[-1].date, datetime.date(2026, 8, 25))
        self.assertEqual(result.daily_activity[-1].page_views, 1)

    def test_brazilian_7_and_30_day_windows_start_at_local_midnight(self) -> None:
        now_utc = datetime.datetime(2026, 8, 25, 3, 30)  # Aug 25, 00:30 BRT
        with self.Session() as db:
            visitor = SiteVisitor(
                visitor_hash="d" * 64,
                first_seen_at=datetime.datetime(2026, 7, 27, 2, 59),
                last_seen_at=datetime.datetime(2026, 8, 19, 3, 0),
                view_count=4,
                last_path="/limites",
            )
            db.add(visitor)
            db.flush()
            db.add_all([
                # Seven-day window starts Aug 19 at 00:00 BRT (03:00 UTC).
                SitePageView(visitor_id=visitor.id, path="/7-in", viewed_at=datetime.datetime(2026, 8, 19, 3, 0)),
                SitePageView(visitor_id=visitor.id, path="/7-out", viewed_at=datetime.datetime(2026, 8, 19, 2, 59)),
                # Thirty-day window starts Jul 27 at 00:00 BRT (03:00 UTC).
                SitePageView(visitor_id=visitor.id, path="/30-in", viewed_at=datetime.datetime(2026, 7, 27, 3, 0)),
                SitePageView(visitor_id=visitor.id, path="/30-out", viewed_at=datetime.datetime(2026, 7, 27, 2, 59)),
            ])
            db.commit()

            result = analytics._build_admin_metrics(db, now=now_utc)

        self.assertEqual(result.page_views.last_7_days, 1)
        self.assertEqual(result.page_views.last_30_days, 3)

    def test_admin_metrics_response_is_never_cacheable(self) -> None:
        response = Response()
        with patch.object(analytics, "SessionLocal", self.Session):
            analytics.admin_metrics(response)

        self.assertEqual(response.headers["cache-control"], "private, no-store, max-age=0")
        self.assertEqual(response.headers["pragma"], "no-cache")


if __name__ == "__main__":
    unittest.main()
