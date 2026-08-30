from __future__ import annotations

import datetime
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from core.deps import get_current_user
from models.database import (
    Book,
    BookFile,
    Chunk,
    SessionLocal,
    User,
    UserReadingProgress,
)
from schemas.reading import (
    ReadingBookMetadata,
    ReadingFileMetadata,
    ReadingHistoryResponse,
    ReadingProgressResponse,
    ReadingProgressUpdate,
)

router = APIRouter()


def _book_for_file(db, book_file: BookFile, requested_book_id: int | None) -> Book:
    book_id = requested_book_id or book_file.book_id
    book = db.get(Book, book_id)
    if book is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Obra nao encontrada.",
        )

    if book.id != book_file.book_id:
        linked = (
            db.query(Chunk.id)
            .filter(
                Chunk.book_id == book.id,
                Chunk.book_file_id == book_file.id,
            )
            .first()
        )
        if linked is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="O PDF informado nao pertence a esta obra.",
            )
    return book


def _page_range(
    db,
    book: Book,
    book_file: BookFile,
    total_pages: int | None,
) -> tuple[int, int | None]:
    # Files owned by a book already start at their first physical page. A
    # logical work contained inside a PL/PG/PO volume starts at its first
    # linked chunk and ends at its last linked page instead.
    if book.id == book_file.book_id:
        return 1, total_pages

    first_page, last_page = (
        db.query(func.min(Chunk.pdf_page), func.max(Chunk.pdf_page))
        .filter(
            Chunk.book_id == book.id,
            Chunk.book_file_id == book_file.id,
            Chunk.pdf_page >= 1,
        )
        .one()
    )
    start_page = max(1, int(first_page or 1))
    end_page = int(last_page) if last_page is not None else None
    # A single indexed page is not enough evidence for the end of a logical
    # work. In that case the API deliberately avoids inventing completion.
    if end_page is None or end_page <= start_page:
        end_page = None
    return start_page, end_page


def _viewer_href(row: UserReadingProgress) -> str:
    query = urlencode(
        {
            "file": f"/api/pdfs/{row.book_file_id}",
            "page": row.current_page,
            "book": row.book_id,
            "reading": "1",
        }
    )
    return f"/viewer/pdf?{query}"


def _progress_state(
    current_page: int,
    *,
    start_page: int,
    end_page: int | None,
    physical_owner: bool,
) -> tuple[float | None, bool]:
    if end_page is None:
        return None, False

    completed = current_page >= end_page
    if physical_owner:
        # A standalone PDF retains its conventional 1..total_pages metric.
        percent = (current_page / end_page) * 100.0
    else:
        if end_page <= start_page:
            return None, False
        percent = ((current_page - start_page) / (end_page - start_page)) * 100.0
    return round(max(0.0, min(100.0, percent)), 2), completed


def _progress_query(db, *, user_id: int, book_id: int, book_file_id: int):
    return db.query(UserReadingProgress).filter(
        UserReadingProgress.user_id == user_id,
        UserReadingProgress.book_id == book_id,
        UserReadingProgress.book_file_id == book_file_id,
    )


def _to_response(
    db,
    row: UserReadingProgress,
    *,
    book: Book | None = None,
    book_file: BookFile | None = None,
) -> ReadingProgressResponse:
    book = book or db.get(Book, row.book_id)
    book_file = book_file or db.get(BookFile, row.book_file_id)
    if book is None or book_file is None:
        # Foreign keys make this impossible in healthy databases, but failing
        # closed avoids returning a resume link to a removed catalog item.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="A obra ou o PDF deste historico nao esta mais disponivel.",
        )

    start_page, end_page = _page_range(db, book, book_file, row.total_pages)
    progress_percent, completed = _progress_state(
        row.current_page,
        start_page=start_page,
        end_page=end_page,
        physical_owner=book.id == book_file.book_id,
    )

    return ReadingProgressResponse(
        book_file_id=book_file.id,
        book_id=book.id,
        revision=max(1, int(row.revision or 1)),
        current_page=row.current_page,
        total_pages=row.total_pages,
        progress_percent=progress_percent,
        completed=completed,
        start_page=start_page,
        end_page=end_page,
        first_opened_at=row.first_opened_at,
        last_read_at=row.last_read_at,
        viewer_href=_viewer_href(row),
        book=ReadingBookMetadata(
            id=book.id,
            title=book.title,
            author=book.author,
            collection=book.collection,
            language=book.language,
            edition_label=book.edition_label,
            canonical_title=book.canonical_title,
            canonical_author=book.canonical_author,
        ),
        file=ReadingFileMetadata(
            id=book_file.id,
            original_filename=book_file.original_filename,
            volume_number=book_file.volume_number,
            editor=book_file.editor,
            translator=book_file.translator,
        ),
    )


def _file_or_404(db, book_file_id: int) -> BookFile:
    book_file = db.get(BookFile, book_file_id)
    if book_file is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF nao encontrado.",
        )
    return book_file


@router.get("/progress/{book_file_id}", response_model=ReadingProgressResponse)
def get_reading_progress(
    book_file_id: int,
    book_id: int | None = Query(default=None, ge=1),
    current_user: User = Depends(get_current_user),
) -> ReadingProgressResponse:
    with SessionLocal() as db:
        book_file = _file_or_404(db, book_file_id)
        book = _book_for_file(db, book_file, book_id)
        row = _progress_query(
            db,
            user_id=current_user.id,
            book_id=book.id,
            book_file_id=book_file.id,
        ).first()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Progresso de leitura nao encontrado.",
            )
        return _to_response(db, row, book=book, book_file=book_file)


@router.put("/progress/{book_file_id}", response_model=ReadingProgressResponse)
def save_reading_progress(
    book_file_id: int,
    payload: ReadingProgressUpdate,
    current_user: User = Depends(get_current_user),
) -> ReadingProgressResponse:
    now = datetime.datetime.utcnow()
    with SessionLocal() as db:
        book_file = _file_or_404(db, book_file_id)
        book = _book_for_file(db, book_file, payload.book_id)
        row = _progress_query(
            db,
            user_id=current_user.id,
            book_id=book.id,
            book_file_id=book_file.id,
        ).with_for_update().first()

        if (
            row is not None
            and payload.base_revision is not None
            and payload.base_revision != row.revision
        ):
            # A delayed request must never overwrite a newer viewer state. The
            # current state is returned with 200 so the client can reconcile
            # its local/offline snapshot without another round trip.
            return _to_response(db, row, book=book, book_file=book_file)

        total_was_sent = "total_pages" in payload.model_fields_set
        effective_total = payload.total_pages if total_was_sent else (
            row.total_pages if row is not None else None
        )
        effective_page = payload.current_page
        if row is not None and payload.event == "open":
            # Opening a deliberate reading link records access but does not
            # move an existing bookmark. Only progress/restart may do that.
            effective_page = row.current_page

        start_page, end_page = _page_range(
            db,
            book,
            book_file,
            effective_total,
        )
        if book.id != book_file.book_id:
            # Logical works inside PL/PG/PO share a much larger physical PDF.
            # Never let their bookmark escape the pages attributed to them.
            effective_page = max(start_page, effective_page)
            if end_page is not None:
                effective_page = min(end_page, effective_page)

        if effective_total is not None and effective_page > effective_total:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A pagina atual nao pode ultrapassar o total de paginas.",
            )
        _, completed = _progress_state(
            effective_page,
            start_page=start_page,
            end_page=end_page,
            physical_owner=book.id == book_file.book_id,
        )
        is_insert = row is None
        if row is None:
            row = UserReadingProgress(
                user_id=current_user.id,
                book_id=book.id,
                book_file_id=book_file.id,
                current_page=effective_page,
                total_pages=effective_total,
                completed=completed,
                revision=1,
                first_opened_at=now,
                last_read_at=now,
            )
            db.add(row)
        else:
            row.current_page = effective_page
            if total_was_sent:
                row.total_pages = payload.total_pages
            row.completed = completed
            row.revision = max(1, int(row.revision or 1)) + 1
            row.last_read_at = now

        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            if not is_insert:
                raise
            # Two first-open requests may both observe no row before either
            # INSERT commits. The unique key chooses the winner; the loser
            # returns that durable state instead of leaking a server error.
            winner = _progress_query(
                db,
                user_id=current_user.id,
                book_id=book.id,
                book_file_id=book_file.id,
            ).with_for_update().first()
            if winner is None:
                raise
            return _to_response(db, winner, book=book, book_file=book_file)
        db.refresh(row)
        return _to_response(db, row, book=book, book_file=book_file)


@router.get("/history", response_model=ReadingHistoryResponse)
def list_reading_history(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
) -> ReadingHistoryResponse:
    with SessionLocal() as db:
        query = db.query(UserReadingProgress).filter(
            UserReadingProgress.user_id == current_user.id
        )
        total = query.count()
        rows = (
            query.order_by(
                UserReadingProgress.last_read_at.desc(),
                UserReadingProgress.id.desc(),
            )
            .offset(offset)
            .limit(limit)
            .all()
        )
        return ReadingHistoryResponse(
            items=[_to_response(db, row) for row in rows],
            total=total,
            limit=limit,
            offset=offset,
        )


@router.delete(
    "/progress/{book_file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def delete_reading_progress(
    book_file_id: int,
    book_id: int | None = Query(default=None, ge=1),
    current_user: User = Depends(get_current_user),
) -> Response:
    with SessionLocal() as db:
        book_file = _file_or_404(db, book_file_id)
        book = _book_for_file(db, book_file, book_id)
        row = _progress_query(
            db,
            user_id=current_user.id,
            book_id=book.id,
            book_file_id=book_file.id,
        ).first()
        if row is not None:
            db.delete(row)
            db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
