"""Dispara a ingestão dos concílios via API HTTP interna do backend.

Isso evita carregar um segundo processo de embedding — usa o modelo já carregado
no processo uvicorn rodando no container.

Uso (dentro do container):
    cd /app && python -m scripts.trigger_ingest_councils [--dry-run] [--delay 2]
"""
from __future__ import annotations

import argparse
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF_ROOT = os.path.join(BACKEND_DIR, "pdfs")
API_BASE = "http://localhost:8000"
API_PREFIX = "/books"
API_KEY = os.environ.get("API_KEY", "UmGKwx6a-aGLzA-_PsakG-u7lSbB1qhlmgD7eUWUWRc")


def _resolve_path(stored_path: str) -> str:
    if os.path.isabs(stored_path):
        return stored_path
    candidate = os.path.join(PDF_ROOT, stored_path)
    if os.path.exists(candidate):
        return candidate
    return os.path.join(PDF_ROOT, stored_path.replace("/", os.sep))


def trigger(dry_run: bool = False, delay: float = 2.0, council_filter: str = "") -> None:
    import requests as req
    from models.database import SessionLocal, Book, BookFile, Chunk

    with SessionLocal() as db:
        query = db.query(Book).filter(
            Book.document_type == "concilio",
            Book.ingest_status == "file_only",
        )
        if council_filter:
            query = query.filter(Book.author.ilike(f"%{council_filter}%"))
        books = query.order_by(Book.id.asc()).all()
        book_data = [(b.id, b.author, b.title, b.language) for b in books]

    print(f"Books para ingerir: {len(book_data)}")
    if not book_data:
        print("Nenhum book pendente.")
        return

    ok = 0
    errors = 0
    headers = {"X-API-Key": API_KEY}

    for book_id, author, title, lang in book_data:
        print(f"\n[{book_id}] {author} / {title} [{lang}]")

        with SessionLocal() as db:
            files = db.query(BookFile).filter(BookFile.book_id == book_id).all()

        if not files:
            print("  Sem BookFiles — pulando.")
            errors += 1
            continue

        book_file = files[0]
        abs_path = _resolve_path(book_file.stored_path)

        if not os.path.exists(abs_path):
            print(f"  Arquivo nao encontrado: {abs_path}")
            errors += 1
            continue

        size_kb = os.path.getsize(abs_path) // 1024
        print(f"  {abs_path} ({size_kb} KB)")

        if dry_run:
            print("  [dry-run] seria enviado para API.")
            continue

        # Verifica se já tem chunks (evitar re-ingestão desnecessária)
        with SessionLocal() as db:
            n_chunks = db.query(Chunk).filter(Chunk.book_id == book_id).count()
        if n_chunks > 0:
            print(f"  Ja tem {n_chunks} chunks — marcando como done.")
            with SessionLocal() as db:
                db.query(Book).filter(Book.id == book_id).update({"ingest_status": "done"})
                db.commit()
            ok += 1
            continue

        filename = os.path.basename(abs_path)
        try:
            with open(abs_path, "rb") as f:
                resp = req.post(
                    f"{API_BASE}{API_PREFIX}/{book_id}/ingest-pdf",
                    headers=headers,
                    files={"file": (filename, f, "application/pdf")},
                    timeout=300,
                )
            if resp.status_code in (200, 201):
                data = resp.json()
                chunks = data.get("chunks_indexed", "?")
                print(f"  OK — {chunks} chunks indexados")
                # Marca como done (ingest-pdf pode não setar se book já existia)
                with SessionLocal() as db:
                    db.query(Book).filter(Book.id == book_id).update({"ingest_status": "done"})
                    db.commit()
                ok += 1
            else:
                print(f"  ERRO {resp.status_code}: {resp.text[:200]}")
                errors += 1
        except Exception as exc:
            print(f"  ERRO: {exc}")
            errors += 1

        if delay > 0:
            time.sleep(delay)

    print(f"\nCONCLUIDO")
    print(f"  OK     : {ok}")
    print(f"  Erros  : {errors}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--council", default="")
    args = parser.parse_args()
    trigger(dry_run=args.dry_run, delay=args.delay, council_filter=args.council)


if __name__ == "__main__":
    main()
