"""
Backfill de editor e tradutor para BookFiles já indexados.

Percorre todos os BookFile no banco, relê as primeiras páginas de cada PDF
em disco (sem OCR completo, sem re-indexar), detecta editora e tradutor,
e atualiza apenas os campos ainda vazios.

Execução:
    cd vera_fidei_starter/backend
    python scripts/backfill_bookfile_metadata.py

Flags (editar no topo do arquivo):
    FORCE_UPDATE  — sobrescreve mesmo campos já preenchidos
    ONLY_PAULUS   — processa apenas arquivos com sinais de Paulus
"""
from __future__ import annotations

import sys
import os

# Garante que o diretório backend esteja no path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.database import SessionLocal, BookFile
from services.ingestion_service import (
    _extract_sample_pages,
    _detect_translator,
    _detect_publisher,
)

# ─── Config ──────────────────────────────────────────────────────────────────

FORCE_UPDATE = False   # True → sobrescreve mesmo campos já preenchidos
ONLY_PAULUS = False    # True → processa só arquivos que mencionam Paulus


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _should_update_editor(bf: BookFile) -> bool:
    return FORCE_UPDATE or not bf.editor


def _should_update_translator(bf: BookFile) -> bool:
    return FORCE_UPDATE or not bf.translator


def _mentions_paulus(text: str, bf: BookFile) -> bool:
    haystack = " ".join([
        text,
        getattr(bf, "original_filename", "") or "",
    ]).lower()
    return "paulus" in haystack


# ─── Main ────────────────────────────────────────────────────────────────────

def run_backfill() -> int:
    updated = 0
    scanned = 0
    skipped = 0

    with SessionLocal() as db:
        book_files: list[BookFile] = db.query(BookFile).all()
        total = len(book_files)
        print(f"Total de BookFiles no banco: {total}\n")

        for bf in book_files:
            need_editor = _should_update_editor(bf)
            need_translator = _should_update_translator(bf)

            if not need_editor and not need_translator:
                print(f"[SKIP] BookFile #{bf.id}: editor e tradutor já preenchidos")
                skipped += 1
                continue

            stored_path = getattr(bf, "stored_path", None)
            if not stored_path or not os.path.isfile(stored_path):
                print(f"[SKIP] BookFile #{bf.id}: arquivo não encontrado em {stored_path!r}")
                skipped += 1
                continue

            sample_pages = _extract_sample_pages(stored_path, n=15)
            full_text = "\n".join(p.get("text", "") for p in sample_pages)

            if not full_text.strip():
                print(f"[SKIP] BookFile #{bf.id}: sem texto extraível (PDF imageado?)")
                skipped += 1
                continue

            scanned += 1

            if ONLY_PAULUS and not _mentions_paulus(full_text, bf):
                print(f"[SKIP] BookFile #{bf.id}: sem sinais de Paulus")
                skipped += 1
                continue

            old_editor = bf.editor
            old_translator = bf.translator

            new_editor = old_editor
            new_translator = old_translator

            if need_editor:
                detected = _detect_publisher(full_text)
                if detected:
                    new_editor = detected

            if need_translator:
                detected = _detect_translator(full_text)
                if detected:
                    new_translator = detected
                # Fallback: quando a editora é a responsável pela tradução
                elif new_editor and not new_translator:
                    new_translator = (
                        f"{new_editor} Editora"
                        if not new_editor.lower().endswith("editora")
                        else new_editor
                    )

            changed = (new_editor != old_editor) or (new_translator != old_translator)

            if changed:
                bf.editor = new_editor
                bf.translator = new_translator
                updated += 1
                print(
                    f"[OK] BookFile #{bf.id} | "
                    f"editor: {old_editor!r} -> {new_editor!r} | "
                    f"tradutor: {old_translator!r} -> {new_translator!r}"
                )
            else:
                print(
                    f"[NOCHANGE] BookFile #{bf.id} | "
                    f"editor={old_editor!r} | tradutor={old_translator!r}"
                )

        db.commit()

    print(f"\n{'='*40}")
    print(f"Escaneados : {scanned}")
    print(f"Atualizados: {updated}")
    print(f"Pulados    : {skipped}")
    return updated


if __name__ == "__main__":
    result = run_backfill()
    sys.exit(0 if result >= 0 else 1)
