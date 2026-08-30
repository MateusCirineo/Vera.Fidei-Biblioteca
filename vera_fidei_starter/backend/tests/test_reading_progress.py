from __future__ import annotations

import datetime
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.routes import reading
from models.database import (
    Base,
    Book,
    BookFile,
    Chunk,
    User,
    UserReadingProgress,
)
from schemas.reading import ReadingProgressUpdate


class ReadingProgressTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(
            self.engine,
            tables=[
                User.__table__,
                Book.__table__,
                BookFile.__table__,
                Chunk.__table__,
                UserReadingProgress.__table__,
            ],
        )
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.Session() as db:
            db.add_all(
                [
                    User(
                        id=1,
                        email="reader@example.com",
                        name="Reader",
                        password_hash="hash",
                    ),
                    User(
                        id=2,
                        email="other@example.com",
                        name="Other",
                        password_hash="hash",
                    ),
                    Book(
                        id=10,
                        collection="PL",
                        title="Patrologia Latina 004",
                        author="J.-P. Migne",
                        language="la",
                        edition_label="Migne",
                    ),
                    Book(
                        id=11,
                        collection="PT",
                        title="De Unitate Ecclesiae",
                        author="Sao Cipriano",
                        language="pt",
                        edition_label="Obra logica",
                        canonical_title="De Unitate Ecclesiae",
                        canonical_author="Sao Cipriano de Cartago",
                    ),
                    Book(
                        id=12,
                        collection="PT",
                        title="Outra obra",
                        author="Outro autor",
                        language="pt",
                        edition_label="Edicao",
                    ),
                ]
            )
            db.flush()
            db.add_all(
                [
                    BookFile(
                        id=100,
                        book_id=10,
                        original_filename="PL004.pdf",
                        stored_path="pdfs/PL004.pdf",
                        volume_number=4,
                        editor="Migne",
                    ),
                    BookFile(
                        id=101,
                        book_id=12,
                        original_filename="outra.pdf",
                        stored_path="pdfs/outra.pdf",
                    ),
                ]
            )
            db.flush()
            db.add_all(
                [
                    Chunk(
                    id=1000,
                    book_id=11,
                    book_file_id=100,
                    chapter_or_section="cap. 6",
                    text="Trecho da obra logica dentro do volume-fonte.",
                    pdf_page=42,
                    ),
                    Chunk(
                        id=1001,
                        book_id=11,
                        book_file_id=100,
                        chapter_or_section="cap. 6 fim",
                        text="Ultima pagina indexada da obra logica.",
                        pdf_page=60,
                    ),
                ]
            )
            db.commit()

        self.current_user = SimpleNamespace(id=1)

    def tearDown(self) -> None:
        self.engine.dispose()

    def save(
        self,
        *,
        book_file_id: int = 100,
        book_id: int | None = 11,
        current_page: int = 42,
        total_pages: int | None = 100,
        event: str = "progress",
        send_total: bool = True,
        base_revision: int | None = None,
    ):
        values = {
            "book_id": book_id,
            "current_page": current_page,
            "event": event,
            "base_revision": base_revision,
        }
        if send_total:
            values["total_pages"] = total_pages
        payload = ReadingProgressUpdate(**values)
        with patch.object(reading, "SessionLocal", self.Session):
            return reading.save_reading_progress(book_file_id, payload, self.current_user)

    def test_saves_logical_book_progress_and_builds_resume_link(self) -> None:
        result = self.save(event="open")

        self.assertEqual(result.book_id, 11)
        self.assertEqual(result.book_file_id, 100)
        self.assertEqual(result.book.title, "De Unitate Ecclesiae")
        self.assertEqual(result.file.original_filename, "PL004.pdf")
        self.assertEqual(result.start_page, 42)
        self.assertEqual(result.end_page, 60)
        self.assertEqual(result.progress_percent, 0.0)
        self.assertFalse(result.completed)
        self.assertEqual(result.revision, 1)
        self.assertIn("file=%2Fapi%2Fpdfs%2F100", result.viewer_href)
        self.assertIn("book=11", result.viewer_href)
        self.assertIn("reading=1", result.viewer_href)

    def test_same_pdf_keeps_independent_owner_and_logical_work_progress(self) -> None:
        self.save(book_id=11, current_page=42)
        self.save(book_id=10, current_page=3)

        with patch.object(reading, "SessionLocal", self.Session):
            history = reading.list_reading_history(25, 0, self.current_user)

        self.assertEqual(history.total, 2)
        self.assertEqual({item.book_id for item in history.items}, {10, 11})
        owner_item = next(item for item in history.items if item.book_id == 10)
        self.assertEqual(owner_item.start_page, 1)
        self.assertEqual(owner_item.end_page, 100)
        self.assertEqual(owner_item.progress_percent, 3.0)

    def test_progress_completion_restart_and_total_preservation(self) -> None:
        first = self.save(current_page=42, total_pages=100)
        completed = self.save(
            current_page=60,
            total_pages=100,
            base_revision=first.revision,
        )
        restarted = self.save(
            current_page=42,
            event="restart",
            send_total=False,
            base_revision=completed.revision,
        )

        self.assertEqual(first.total_pages, 100)
        self.assertTrue(completed.completed)
        self.assertEqual(completed.progress_percent, 100.0)
        self.assertEqual(restarted.total_pages, 100)
        self.assertFalse(restarted.completed)
        self.assertEqual(restarted.current_page, 42)
        self.assertEqual(restarted.first_opened_at, first.first_opened_at)
        self.assertGreaterEqual(restarted.last_read_at, first.last_read_at)
        self.assertEqual((first.revision, completed.revision, restarted.revision), (1, 2, 3))

    def test_explicit_null_can_clear_an_incorrect_total(self) -> None:
        first = self.save(book_id=10, current_page=2, total_pages=100)
        result = self.save(
            book_id=10,
            current_page=3,
            total_pages=None,
            send_total=True,
            base_revision=first.revision,
        )
        self.assertIsNone(result.total_pages)
        self.assertIsNone(result.end_page)
        self.assertIsNone(result.progress_percent)
        self.assertFalse(result.completed)

    def test_alias_without_a_reliable_end_never_invents_completion(self) -> None:
        with self.Session() as db:
            db.query(Chunk).filter(Chunk.id == 1001).delete()
            db.commit()

        result = self.save(current_page=42, total_pages=100)

        self.assertEqual(result.start_page, 42)
        self.assertIsNone(result.end_page)
        self.assertIsNone(result.progress_percent)
        self.assertFalse(result.completed)

    def test_revision_conflict_returns_current_state_without_overwrite(self) -> None:
        first = self.save(current_page=42)
        second = self.save(current_page=50, base_revision=first.revision)
        stale = self.save(current_page=43, base_revision=first.revision)

        self.assertEqual(second.revision, 2)
        self.assertEqual(stale.revision, 2)
        self.assertEqual(stale.current_page, 50)
        self.assertEqual(stale.last_read_at, second.last_read_at)
        with self.Session() as db:
            stored = db.query(UserReadingProgress).filter_by(book_id=11).one()
            self.assertEqual((stored.current_page, stored.revision), (50, 2))

    def test_existing_open_cannot_regress_a_saved_page(self) -> None:
        first = self.save(current_page=50)
        reopened = self.save(
            current_page=55,
            event="open",
            base_revision=first.revision,
        )

        self.assertEqual(reopened.current_page, 50)
        self.assertEqual(reopened.revision, 2)

    def test_alias_progress_is_clamped_to_its_logical_page_range(self) -> None:
        after_end = self.save(current_page=99, total_pages=100)
        before_start = self.save(
            current_page=1,
            total_pages=100,
            event="restart",
            base_revision=after_end.revision,
        )

        self.assertEqual(after_end.current_page, 60)
        self.assertTrue(after_end.completed)
        self.assertIn("page=60", after_end.viewer_href)
        self.assertEqual(before_start.current_page, 42)
        self.assertFalse(before_start.completed)
        self.assertIn("page=42", before_start.viewer_href)

    def test_first_insert_unique_race_returns_the_winning_state(self) -> None:
        route_db = self.Session()

        def lose_insert_race() -> None:
            route_db.rollback()
            with self.Session() as winner_db:
                winner_db.add(
                    UserReadingProgress(
                        user_id=1,
                        book_id=11,
                        book_file_id=100,
                        current_page=50,
                        total_pages=100,
                        completed=False,
                        revision=1,
                    )
                )
                winner_db.commit()
            raise IntegrityError("INSERT", {}, Exception("unique violation"))

        payload = ReadingProgressUpdate(
            book_id=11,
            current_page=42,
            total_pages=100,
            event="open",
        )
        with (
            patch.object(reading, "SessionLocal", lambda: route_db),
            patch.object(route_db, "commit", side_effect=lose_insert_race),
        ):
            result = reading.save_reading_progress(100, payload, self.current_user)

        self.assertEqual(result.current_page, 50)
        self.assertEqual(result.revision, 1)

    def test_response_datetimes_are_explicit_utc(self) -> None:
        result = self.save()
        payload = result.model_dump(mode="json")

        self.assertTrue(payload["first_opened_at"].endswith("Z"))
        self.assertTrue(payload["last_read_at"].endswith("Z"))

    def test_rejects_page_outside_total_and_unrelated_logical_book(self) -> None:
        with self.assertRaises(ValidationError):
            ReadingProgressUpdate(current_page=101, total_pages=100)
        with self.assertRaises(ValidationError):
            ReadingProgressUpdate(current_page=1, base_revision=0)

        with self.assertRaises(HTTPException) as raised:
            self.save(book_id=12, current_page=1, total_pages=10)
        self.assertEqual(raised.exception.status_code, 422)

    def test_missing_pdf_is_not_silently_added(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            self.save(book_file_id=999)
        self.assertEqual(raised.exception.status_code, 404)

    def test_progress_is_private_to_the_signed_in_user(self) -> None:
        self.save()
        with (
            patch.object(reading, "SessionLocal", self.Session),
            self.assertRaises(HTTPException) as raised,
        ):
            reading.get_reading_progress(100, 11, SimpleNamespace(id=2))
        self.assertEqual(raised.exception.status_code, 404)

    def test_history_is_sorted_and_paginated(self) -> None:
        self.save(book_id=11, current_page=42)
        self.save(book_id=10, current_page=2)
        with self.Session() as db:
            logical = db.query(UserReadingProgress).filter_by(book_id=11).one()
            owner = db.query(UserReadingProgress).filter_by(book_id=10).one()
            logical.last_read_at = datetime.datetime(2026, 8, 28, 10, 0, 0)
            owner.last_read_at = datetime.datetime(2026, 8, 29, 10, 0, 0)
            db.commit()

        with patch.object(reading, "SessionLocal", self.Session):
            first_page = reading.list_reading_history(1, 0, self.current_user)
            second_page = reading.list_reading_history(1, 1, self.current_user)

        self.assertEqual(first_page.total, 2)
        self.assertEqual(first_page.limit, 1)
        self.assertEqual(first_page.items[0].book_id, 10)
        self.assertEqual(second_page.items[0].book_id, 11)

    def test_delete_is_idempotent_and_scoped_to_logical_work(self) -> None:
        self.save(book_id=11)
        self.save(book_id=10, current_page=2)
        with patch.object(reading, "SessionLocal", self.Session):
            first = reading.delete_reading_progress(100, 11, self.current_user)
            second = reading.delete_reading_progress(100, 11, self.current_user)

        self.assertEqual(first.status_code, 204)
        self.assertEqual(second.status_code, 204)
        with self.Session() as db:
            remaining = db.query(UserReadingProgress).all()
            self.assertEqual(len(remaining), 1)
            self.assertEqual(remaining[0].book_id, 10)


if __name__ == "__main__":
    unittest.main()
