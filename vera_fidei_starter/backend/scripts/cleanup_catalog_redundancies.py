"""Remove catalog references that duplicate the exact same stored PDF.

The command is conservative and dry-run by default. It only removes BookFile
rows attached to books with no chunks when the exact stored_path is already
attached to a populated version of the same work and author. Unique language
files are moved to that populated work before the empty shell is removed.

It also converts the standalone De Unitate Ecclesiae excerpt into a
location-only pointer to chapter 6 in PL004, without retaining quotation text.
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/app")

from elasticsearch.helpers import bulk  # noqa: E402
from sqlalchemy import func  # noqa: E402

from models.database import (  # noqa: E402
    Book,
    BookFile,
    Chunk,
    SessionLocal,
    Translation,
    UserFavorite,
    VerifiedPageReview,
    VerifiedPassage,
)
from search.text_search import ES_INDEX, TextSearchClient  # noqa: E402


BACKUP_ROOT = Path("/app/pdfs/.catalog_cleanup_backups")
DE_UNITATE_BOOK_ID = 1
DE_UNITATE_CHUNK_ID = 1
DE_UNITATE_SOURCE_BOOK_ID = 1777
DE_UNITATE_SOURCE_FILE_ID = 3285
DE_UNITATE_SOURCE_PAGE = 256
MISMATCHED_FILE_ID = 3048
MISMATCHED_FILE_REPLACEMENT_ID = 3581
# These three PDFs differ only by the generated heading omitting the word
# "Papa"; their complete normalized bodies are otherwise identical to files
# 3126/3127/3128 (similarity > 0.9996), with the same Vatican.va edition and
# language. The populated files remain authoritative.
SEMANTIC_DUPLICATE_FILE_IDS = {3533, 3534, 3535}

# Exact-byte duplicates inside the same catalog work. The left-hand BookFile
# has no chunks; the right-hand one is the indexed copy that remains.
NO_CHUNK_DUPLICATE_TO_KEEPER = {
    3290: 3877,
    3291: 3879,
    3292: 3880,
    3293: 3882,
    3294: 3884,
    3295: 3886,
    3297: 3891,
    3298: 3892,
    3299: 3893,
    3300: 3894,
    3301: 3895,
    3302: 3896,
    3303: 3897,
    3304: 3898,
    3305: 3899,
    3306: 3900,
    3307: 3901,
    3308: 3902,
    3309: 3903,
    3310: 3904,
    3311: 3905,
    3312: 3906,
    3313: 3907,
    3324: 3930,
    3325: 3931,
    3326: 3932,
    3322: 400,
}

# Both copies have identical PDF bytes and identical ordered chunk text. The
# keeper has the correct catalog identity/metadata.
CHUNK_DUPLICATE_TO_KEEPER = {
    399: 3107,   # Lumen Fidei
    4012: 4082,  # Sobre a Música - Ecclesiae/CEDET, Felipe Lesage
    4063: 4089,  # O Pai Nosso e a Ave Maria - Permanência
}
DUPLICATE_BOOK_TO_KEEPER = {2048: 2118, 2099: 2125}

# Visual inspection proved that these four identically hashed files contain
# the Portuguese Code of Canon Law, despite three works claiming otherwise.
# File 2372 is retained as the distinct Portuguese (Portugal) 4th edition and
# is moved to the correct Code record; the other copies and their chunks go.
CANON_LAW_BOOK_ID = 1827
CANON_LAW_KEEPER_FILE_ID = 2372
CANON_LAW_STORED_PATH = (
    "gdrive://vera-fidei/pdfs/documentos_igreja/codigo_direito_canonico/"
    "Codigo_de_Direito_Canonico_1983_PT_4ed.pdf"
)
WRONG_SOURCE_FILE_IDS = {2365, 3296, 3888}


def _norm(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", (value or "").casefold())
    return "".join(char for char in text if not unicodedata.combining(char) and char.isalnum())


def _snapshot_row(row, fields: tuple[str, ...]) -> dict:
    return {field: getattr(row, field) for field in fields}


def _ordered_chunk_text(db, file_id: int) -> str:
    rows = (
        db.query(Chunk.text)
        .filter(Chunk.book_file_id == file_id)
        .order_by(Chunk.sequence_index, Chunk.id)
        .all()
    )
    return "\n".join(text for (text,) in rows)


def _es_doc(book: Book, chunk: Chunk) -> dict:
    return {
        "book_id": book.id,
        "book_file_id": chunk.book_file_id,
        "text": chunk.text,
        "author": book.author,
        "work_title": book.title,
        "collection": book.collection,
        "volume": chunk.volume,
        "column_start": chunk.column_start,
        "language": book.language,
        "pdf_page": chunk.pdf_page,
        "edition_label": book.edition_label,
        "chapter_or_section": chunk.chapter_or_section,
        "char_offset_start": chunk.char_offset_start,
        "char_offset_end": chunk.char_offset_end,
        "extraction_method": chunk.extraction_method,
        "source_fidelity": chunk.source_fidelity,
        "fidelity_score": chunk.fidelity_score,
    }


def _inventory(db) -> dict:
    books = db.query(Book).order_by(Book.id).all()
    files = db.query(BookFile).order_by(BookFile.id).all()
    chunks = db.query(Chunk).order_by(Chunk.id).all()
    chunk_counts: dict[int, int] = defaultdict(int)
    file_chunk_counts: dict[int, int] = defaultdict(int)
    for chunk in chunks:
        chunk_counts[chunk.book_id] += 1
        if chunk.book_file_id is not None:
            file_chunk_counts[chunk.book_file_id] += 1

    files_by_path: dict[str, list[BookFile]] = defaultdict(list)
    files_by_book: dict[int, list[BookFile]] = defaultdict(list)
    for file in files:
        files_by_path[file.stored_path].append(file)
        files_by_book[file.book_id].append(file)
    books_by_id = {book.id: book for book in books}

    empty_books = {book.id for book in books if chunk_counts[book.id] == 0}
    redundant_files: set[int] = set()
    target_candidates: dict[int, set[int]] = defaultdict(set)
    for path_files in files_by_path.values():
        if len(path_files) < 2:
            continue
        populated = [file for file in path_files if file.book_id not in empty_books]
        if not populated:
            continue
        for file in path_files:
            if file.book_id not in empty_books or file_chunk_counts[file.id] != 0:
                continue
            source_book = books_by_id[file.book_id]
            matching = [
                candidate
                for candidate in populated
                if _norm(books_by_id[candidate.book_id].title) == _norm(source_book.title)
                and _norm(books_by_id[candidate.book_id].author) == _norm(source_book.author)
                and _norm(candidate.editor) == _norm(file.editor)
                and _norm(candidate.translator) == _norm(file.translator)
            ]
            if not matching:
                continue
            redundant_files.add(file.id)
            target_candidates[file.book_id].update(candidate.book_id for candidate in matching)

    moves: list[dict] = []
    deletes: list[int] = []
    book_deletes: list[int] = []
    for book_id in sorted(target_candidates):
        source_book = books_by_id[book_id]
        candidates = sorted(target_candidates[book_id])
        if len(candidates) != 1:
            raise RuntimeError(f"book {book_id} has ambiguous populated targets: {candidates}")
        target_id = candidates[0]
        for file in files_by_book[book_id]:
            if file.id in redundant_files or file.id in SEMANTIC_DUPLICATE_FILE_IDS:
                deletes.append(file.id)
            else:
                moves.append({"file_id": file.id, "from_book_id": book_id, "to_book_id": target_id})
        book_deletes.append(book_id)

    duplicate_groups_before = sum(1 for rows in files_by_path.values() if len(rows) > 1)
    content_file_deletes = sorted(
        set(NO_CHUNK_DUPLICATE_TO_KEEPER)
        | set(CHUNK_DUPLICATE_TO_KEEPER)
        | WRONG_SOURCE_FILE_IDS
    )
    all_file_deletes = sorted(
        set(deletes) | set(content_file_deletes) | {MISMATCHED_FILE_ID}
    )
    return {
        "books_before": len(books),
        "files_before": len(files),
        "chunks_before": len(chunks),
        "duplicate_groups_before": duplicate_groups_before,
        "redundant_file_deletes": sorted(deletes),
        "content_file_deletes": content_file_deletes,
        "all_file_deletes": all_file_deletes,
        "file_moves": moves,
        "empty_book_deletes": sorted(book_deletes),
        "duplicate_book_merges": DUPLICATE_BOOK_TO_KEEPER,
    }


def _validate_fixed_records(db) -> None:
    logical = db.get(Book, DE_UNITATE_BOOK_ID)
    source_file = db.get(BookFile, DE_UNITATE_SOURCE_FILE_ID)
    chunk = db.get(Chunk, DE_UNITATE_CHUNK_ID)
    replacement = db.get(BookFile, MISMATCHED_FILE_REPLACEMENT_ID)
    mismatch = db.get(BookFile, MISMATCHED_FILE_ID)
    if logical is None or logical.title != "De Unitate Ecclesiae":
        raise RuntimeError("De Unitate Ecclesiae catalog record changed")
    if source_file is None or source_file.book_id != DE_UNITATE_SOURCE_BOOK_ID:
        raise RuntimeError("PL004 source file mapping changed")
    if chunk is None or chunk.book_id != DE_UNITATE_BOOK_ID:
        raise RuntimeError("De Unitate Ecclesiae locator chunk changed")
    if replacement is None or replacement.book_id != 1596:
        raise RuntimeError("Paul VI replacement file mapping changed")
    if mismatch is None or mismatch.book_id != 1596:
        raise RuntimeError("known mismatched BookFile mapping changed")

    for duplicate_id, keeper_id in NO_CHUNK_DUPLICATE_TO_KEEPER.items():
        duplicate = db.get(BookFile, duplicate_id)
        keeper = db.get(BookFile, keeper_id)
        if duplicate is None or keeper is None or duplicate.book_id != keeper.book_id:
            raise RuntimeError(f"same-book duplicate mapping changed: {duplicate_id}->{keeper_id}")
        if db.query(Chunk.id).filter(Chunk.book_file_id == duplicate_id).first():
            raise RuntimeError(f"expected BookFile {duplicate_id} to have no chunks")

    for duplicate_id, keeper_id in CHUNK_DUPLICATE_TO_KEEPER.items():
        duplicate = db.get(BookFile, duplicate_id)
        keeper = db.get(BookFile, keeper_id)
        if duplicate is None or keeper is None:
            raise RuntimeError(f"content duplicate mapping changed: {duplicate_id}->{keeper_id}")
        duplicate_text = _ordered_chunk_text(db, duplicate_id)
        keeper_text = _ordered_chunk_text(db, keeper_id)
        if not duplicate_text or duplicate_text != keeper_text:
            raise RuntimeError(f"chunk text is not identical: {duplicate_id}->{keeper_id}")

    canon_file = db.get(BookFile, CANON_LAW_KEEPER_FILE_ID)
    canon_book = db.get(Book, CANON_LAW_BOOK_ID)
    if canon_file is None or canon_file.book_id != 674 or canon_book is None:
        raise RuntimeError("Code of Canon Law correction mapping changed")
    if db.query(VerifiedPassage.id).filter(
        VerifiedPassage.book_file_id.in_(set(NO_CHUNK_DUPLICATE_TO_KEEPER) | set(CHUNK_DUPLICATE_TO_KEEPER) | WRONG_SOURCE_FILE_IDS)
    ).first():
        raise RuntimeError("refusing cleanup because a file to delete has a verified passage")
    if db.query(VerifiedPageReview.id).filter(
        VerifiedPageReview.book_file_id.in_(set(NO_CHUNK_DUPLICATE_TO_KEEPER) | set(CHUNK_DUPLICATE_TO_KEEPER) | WRONG_SOURCE_FILE_IDS)
    ).first():
        raise RuntimeError("refusing cleanup because a file to delete has a verified page review")


def _backup(db, plan: dict) -> Path:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = BACKUP_ROOT / f"catalog_cleanup_{stamp}.json"
    file_ids = set(plan["all_file_deletes"]) | {
        move["file_id"] for move in plan["file_moves"]
    } | set(NO_CHUNK_DUPLICATE_TO_KEEPER.values()) | set(CHUNK_DUPLICATE_TO_KEEPER.values()) | {
        DE_UNITATE_SOURCE_FILE_ID,
        MISMATCHED_FILE_REPLACEMENT_ID,
        CANON_LAW_KEEPER_FILE_ID,
    }
    affected_file_rows = db.query(BookFile).filter(BookFile.id.in_(file_ids)).all()
    book_ids = (
        set(plan["empty_book_deletes"])
        | set(DUPLICATE_BOOK_TO_KEEPER)
        | set(DUPLICATE_BOOK_TO_KEEPER.values())
        | {DE_UNITATE_BOOK_ID, 1596, CANON_LAW_BOOK_ID}
        | {row.book_id for row in affected_file_rows}
    )
    chunk_ids = [
        row.id
        for row in db.query(Chunk).filter(
            (Chunk.book_id.in_(book_ids)) | (Chunk.book_file_id.in_(file_ids))
        )
    ]
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "plan": plan,
        "books": [
            _snapshot_row(row, tuple(column.name for column in Book.__table__.columns))
            for row in db.query(Book).filter(Book.id.in_(book_ids)).order_by(Book.id)
        ],
        "book_files": [
            _snapshot_row(row, tuple(column.name for column in BookFile.__table__.columns))
            for row in db.query(BookFile).filter(BookFile.id.in_(file_ids)).order_by(BookFile.id)
        ],
        "chunks": [
            _snapshot_row(row, tuple(column.name for column in Chunk.__table__.columns))
            for row in db.query(Chunk).filter(Chunk.id.in_(chunk_ids)).order_by(Chunk.id)
        ],
        "translations": [
            _snapshot_row(row, tuple(column.name for column in Translation.__table__.columns))
            for row in db.query(Translation).filter(Translation.chunk_id.in_(chunk_ids)).order_by(Translation.id)
        ],
        "verified_passages": [
            _snapshot_row(row, tuple(column.name for column in VerifiedPassage.__table__.columns))
            for row in db.query(VerifiedPassage)
            .filter((VerifiedPassage.book_id.in_(book_ids)) | (VerifiedPassage.book_file_id.in_(file_ids)))
            .order_by(VerifiedPassage.id)
        ],
        "verified_page_reviews": [
            _snapshot_row(row, tuple(column.name for column in VerifiedPageReview.__table__.columns))
            for row in db.query(VerifiedPageReview)
            .filter((VerifiedPageReview.book_id.in_(book_ids)) | (VerifiedPageReview.book_file_id.in_(file_ids)))
            .order_by(VerifiedPageReview.id)
        ],
        "favorites": [
            _snapshot_row(row, tuple(column.name for column in UserFavorite.__table__.columns))
            for row in db.query(UserFavorite)
            .filter(UserFavorite.kind == "book", UserFavorite.item_id.in_([str(value) for value in book_ids]))
            .order_by(UserFavorite.id)
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, default=str, indent=2), encoding="utf-8")
    return path


def _merge_book_favorites(db, duplicate_book_id: int, keeper_book_id: int) -> None:
    keeper = db.get(Book, keeper_book_id)
    rows = (
        db.query(UserFavorite)
        .filter(UserFavorite.kind == "book", UserFavorite.item_id == str(duplicate_book_id))
        .all()
    )
    for favorite in rows:
        existing = (
            db.query(UserFavorite.id)
            .filter(
                UserFavorite.user_id == favorite.user_id,
                UserFavorite.kind == "book",
                UserFavorite.item_id == str(keeper_book_id),
            )
            .first()
        )
        if existing:
            db.delete(favorite)
            continue
        favorite.item_id = str(keeper_book_id)
        favorite.title = keeper.title
        favorite.subtitle = " - ".join(
            value for value in (keeper.author, keeper.edition_label or keeper.source_label) if value
        ) or None
        favorite.href = f"/biblioteca/{keeper_book_id}"
        favorite.source = keeper.collection or keeper.source_label or None


def _delete_chunks_for_files(db, file_ids: set[int]) -> list[int]:
    chunk_ids = [
        chunk_id
        for (chunk_id,) in db.query(Chunk.id).filter(Chunk.book_file_id.in_(file_ids)).all()
    ]
    if not chunk_ids:
        return []
    db.query(Translation).filter(Translation.chunk_id.in_(chunk_ids)).delete(
        synchronize_session=False
    )
    db.query(Chunk).filter(Chunk.id.in_(chunk_ids)).delete(synchronize_session=False)
    return chunk_ids


def run(apply: bool) -> dict:
    with SessionLocal() as db:
        _validate_fixed_records(db)
        plan = _inventory(db)
        if len(plan["redundant_file_deletes"]) != 138:
            raise RuntimeError(
                f"expected 138 proven redundant files, found {len(plan['redundant_file_deletes'])}"
            )
        if len(plan["empty_book_deletes"]) != 34:
            raise RuntimeError(
                f"expected 34 empty duplicate books, found {len(plan['empty_book_deletes'])}"
            )
        if len(plan["all_file_deletes"]) != 172:
            raise RuntimeError(
                f"expected 172 proven redundant/wrong files, found {len(plan['all_file_deletes'])}"
            )
        if not apply:
            return {"status": "dry_run", **plan}

        backup = _backup(db, plan)
        deleted_chunk_ids: list[int] = []

        for move in plan["file_moves"]:
            file = db.get(BookFile, move["file_id"])
            if file is None or file.book_id != move["from_book_id"]:
                raise RuntimeError(f"BookFile move precondition failed: {move}")
            file.book_id = move["to_book_id"]

        db.query(BookFile).filter(BookFile.id.in_(plan["redundant_file_deletes"])).delete(
            synchronize_session=False
        )
        db.flush()
        for book_id in plan["empty_book_deletes"]:
            if db.query(Chunk.id).filter(Chunk.book_id == book_id).first():
                raise RuntimeError(f"refusing to delete populated book {book_id}")
            if db.query(BookFile.id).filter(BookFile.book_id == book_id).first():
                raise RuntimeError(f"refusing to delete book {book_id} with remaining files")
            db.query(Book).filter(Book.id == book_id).delete(synchronize_session=False)

        # One path was triplicated. File 3048 belongs to the wrong pope/work;
        # its four Paul VI chunks are relinked to the existing Paul VI PDF.
        db.query(Chunk).filter(Chunk.book_file_id == MISMATCHED_FILE_ID).update(
            {Chunk.book_file_id: MISMATCHED_FILE_REPLACEMENT_ID},
            synchronize_session=False,
        )
        db.query(VerifiedPassage).filter(
            VerifiedPassage.book_file_id == MISMATCHED_FILE_ID
        ).update(
            {VerifiedPassage.book_file_id: MISMATCHED_FILE_REPLACEMENT_ID},
            synchronize_session=False,
        )
        db.query(VerifiedPageReview).filter(
            VerifiedPageReview.book_file_id == MISMATCHED_FILE_ID
        ).update(
            {VerifiedPageReview.book_file_id: MISMATCHED_FILE_REPLACEMENT_ID},
            synchronize_session=False,
        )
        db.query(BookFile).filter(BookFile.id == MISMATCHED_FILE_ID).delete(
            synchronize_session=False
        )

        # Preserve the indexed copy of each exact-byte duplicate and enrich it
        # with the editor metadata from the redundant row.
        for duplicate_id, keeper_id in NO_CHUNK_DUPLICATE_TO_KEEPER.items():
            duplicate = db.get(BookFile, duplicate_id)
            keeper = db.get(BookFile, keeper_id)
            if duplicate.editor and not keeper.editor:
                keeper.editor = duplicate.editor
            if duplicate.translator and not keeper.translator:
                keeper.translator = duplicate.translator

        # One of the duplicate groups was actually a Portuguese Code of Canon
        # Law edition stored beneath three unrelated work titles. Keep one
        # source, move it to the proper book, and discard the false attributions.
        canon_file = db.get(BookFile, CANON_LAW_KEEPER_FILE_ID)
        canon_file.book_id = CANON_LAW_BOOK_ID
        canon_file.stored_path = CANON_LAW_STORED_PATH
        canon_file.original_filename = "Código de Direito Canónico — 4ª edição revista (Portugal).pdf"
        canon_file.editor = "Conferência Episcopal Portuguesa / Editorial Apostolado da Oração"
        canon_file.translator = "António Leite, S.J. (rev. Serafim Ferreira e Silva et al.)"
        canon_chunks = (
            db.query(Chunk).filter(Chunk.book_file_id == CANON_LAW_KEEPER_FILE_ID).all()
        )
        for chunk in canon_chunks:
            chunk.book_id = CANON_LAW_BOOK_ID
            chunk.chunk_author = "Santa Sé"

        deleted_chunk_ids.extend(
            _delete_chunks_for_files(
                db,
                set(CHUNK_DUPLICATE_TO_KEEPER) | WRONG_SOURCE_FILE_IDS,
            )
        )
        db.query(BookFile).filter(BookFile.id.in_(plan["content_file_deletes"])).delete(
            synchronize_session=False
        )

        # Correct the metadata proven by each PDF's own title/copyright pages.
        music_file = db.get(BookFile, 4082)
        music_file.editor = "Ecclesiae / CEDET"
        music_file.translator = "Felipe Lesage"
        music_book = db.get(Book, 2118)
        music_book.edition_label = "Ecclesiae, 1ª edição, 2019"
        music_book.source_label = "Ecclesiae / CEDET"

        prayer_file = db.get(BookFile, 4089)
        prayer_file.editor = "Permanência"
        prayer_file.translator = "Um monge de Fontgombault"
        prayer_book = db.get(Book, 2125)
        prayer_book.edition_label = "Edição eletrônica Permanência, 2003"
        prayer_book.source_label = "Permanência"

        db.get(BookFile, 400).editor = "Vatican.va"
        for book_id in (1780, 1781, 1782, 1783):
            book = db.get(Book, book_id)
            book.language = "multi"
            book.edition_label = "Vatican.va PDFs multilingues"

        for duplicate_book_id, keeper_book_id in DUPLICATE_BOOK_TO_KEEPER.items():
            _merge_book_favorites(db, duplicate_book_id, keeper_book_id)
            if db.query(Chunk.id).filter(Chunk.book_id == duplicate_book_id).first():
                raise RuntimeError(f"duplicate book {duplicate_book_id} still has chunks")
            if db.query(BookFile.id).filter(BookFile.book_id == duplicate_book_id).first():
                raise RuntimeError(f"duplicate book {duplicate_book_id} still has files")
            db.query(Book).filter(Book.id == duplicate_book_id).delete(synchronize_session=False)

        # Keep only the exact source locator. No standalone quotation or
        # translation remains; the UI resolves the shared PL004 file at p. 256.
        locator = db.get(Chunk, DE_UNITATE_CHUNK_ID)
        locator.text = ""
        locator.book_file_id = DE_UNITATE_SOURCE_FILE_ID
        locator.chapter_or_section = "Cap. 6 — PL004, col. 503"
        locator.pdf_page = DE_UNITATE_SOURCE_PAGE
        locator.column_start = 503
        locator.column_end = 503
        locator.extraction_method = "source_locator"
        locator.source_fidelity = "location_only"
        locator.fidelity_score = None
        locator.fidelity_reasons = "text_removed_by_owner;source=PL004.pdf#page=256;column=503"
        db.query(Translation).filter(Translation.chunk_id == DE_UNITATE_CHUNK_ID).delete(
            synchronize_session=False
        )
        db.query(VerifiedPassage).filter(
            VerifiedPassage.book_id == DE_UNITATE_BOOK_ID
        ).delete(synchronize_session=False)

        db.flush()
        duplicate_groups_after = (
            db.query(BookFile.stored_path)
            .group_by(BookFile.stored_path)
            .having(func.count(BookFile.id) > 1)
            .count()
        )
        if duplicate_groups_after != 0:
            raise RuntimeError(f"duplicate paths remain after cleanup: {duplicate_groups_after}")
        expected_books = plan["books_before"] - len(plan["empty_book_deletes"]) - len(DUPLICATE_BOOK_TO_KEEPER)
        expected_files = plan["files_before"] - len(plan["all_file_deletes"])
        expected_chunks = plan["chunks_before"] - len(deleted_chunk_ids)
        if db.query(func.count(Book.id)).scalar() != expected_books:
            raise RuntimeError("book count after cleanup differs from the proven plan")
        if db.query(func.count(BookFile.id)).scalar() != expected_files:
            raise RuntimeError("file count after cleanup differs from the proven plan")
        if db.query(func.count(Chunk.id)).scalar() != expected_chunks:
            raise RuntimeError("chunk count after cleanup differs from the proven plan")
        db.commit()

    text_search = TextSearchClient()
    delete_actions = [
        {"_op_type": "delete", "_index": ES_INDEX, "_id": str(chunk_id)}
        for chunk_id in [DE_UNITATE_CHUNK_ID, *deleted_chunk_ids]
    ]
    bulk(text_search.es, delete_actions, raise_on_error=False, raise_on_exception=False)
    with SessionLocal() as db:
        reindex_chunks = (
            db.query(Chunk)
            .filter(
                (Chunk.book_file_id == CANON_LAW_KEEPER_FILE_ID)
                | (Chunk.book_file_id == MISMATCHED_FILE_REPLACEMENT_ID)
            )
            .order_by(Chunk.id)
            .all()
        )
        books = {book.id: book for book in db.query(Book).filter(Book.id.in_({row.book_id for row in reindex_chunks})).all()}
        text_search.index_chunks(
            [(chunk.id, _es_doc(books[chunk.book_id], chunk)) for chunk in reindex_chunks]
        )
    return {
        "status": "applied",
        **plan,
        "duplicate_groups_after": 0,
        "deleted_chunks": len(deleted_chunk_ids),
        "books_after": plan["books_before"] - 36,
        "files_after": plan["files_before"] - 172,
        "chunks_after": plan["chunks_before"] - len(deleted_chunk_ids),
        "de_unitate": {
            "book_id": DE_UNITATE_BOOK_ID,
            "text_removed": True,
            "source_book_id": DE_UNITATE_SOURCE_BOOK_ID,
            "source_file_id": DE_UNITATE_SOURCE_FILE_ID,
            "pdf_page": DE_UNITATE_SOURCE_PAGE,
            "column": 503,
        },
        "backup": str(backup),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.apply), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
