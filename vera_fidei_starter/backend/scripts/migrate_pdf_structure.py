"""
Migra os PDFs de encíclicas e documentos papais para a estrutura:
  pdfs/{tipo}/Papa {Nome}/{Título da Obra}/{titulo-slug}_{lang}.pdf

Executa:
  cd vera_fidei_starter/backend
  python scripts/migrate_pdf_structure.py [--dry-run]
"""
from __future__ import annotations
import argparse
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[àáâãä]", "a", text)
    text = re.sub(r"[èéêë]", "e", text)
    text = re.sub(r"[ìíîï]", "i", text)
    text = re.sub(r"[òóôõö]", "o", text)
    text = re.sub(r"[ùúûü]", "u", text)
    text = re.sub(r"[ç]", "c", text)
    text = re.sub(r"[ñ]", "n", text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def _detect_lang_from_filename(filename: str) -> str | None:
    """Extract lang code from filenames like lumen-fidei_francisco_2013_pt.pdf"""
    base = os.path.splitext(filename)[0]
    parts = base.split("_")
    known = {"pt", "en", "es", "fr", "de", "it", "la", "po"}
    for part in reversed(parts):
        if part.lower() in known:
            return part.lower()
    return None


def _title_to_work_folder(title: str) -> str:
    """Book title → safe folder name (preserve accents, strip unsafe chars)."""
    # Remove characters not safe for folder names
    safe = re.sub(r'[<>:"/\\|?*]', "", title)
    return safe.strip()


def migrate(dry_run: bool = False) -> None:
    from models.database import SessionLocal, BookFile, Book

    with SessionLocal() as db:
        # Get all BookFiles from documentos section that still have old-style paths
        files = (
            db.query(BookFile)
            .join(Book, BookFile.book_id == Book.id)
            .filter(Book.library_section == "documentos")
            .all()
        )

        moved = 0
        skipped = 0
        errors = 0

        for bf in files:
            old_path = bf.stored_path
            if not old_path:
                continue

            # Normalise to forward slashes for checking
            old_path_norm = old_path.replace("\\", "/")

            # Skip if file doesn't exist
            if not os.path.isfile(old_path):
                # Maybe stored as relative path from backend dir
                abs_path = os.path.join(BACKEND_DIR, old_path)
                if os.path.isfile(abs_path):
                    old_path = abs_path
                else:
                    print(f"  SKIP (not found): {old_path}")
                    skipped += 1
                    continue

            book = db.query(Book).filter(Book.id == bf.book_id).first()
            if not book:
                continue

            title = book.title or "Desconhecido"
            work_folder = _title_to_work_folder(title)
            parent_dir = os.path.dirname(old_path)

            # Check if already in a work subfolder (i.e., parent folder name == work title)
            parent_name = os.path.basename(parent_dir)
            # If parent_name is already the work title folder, skip
            if parent_name == work_folder:
                skipped += 1
                continue

            # Determine language
            old_filename = os.path.basename(old_path)
            lang = _detect_lang_from_filename(old_filename)

            # Build new filename
            slug = _slugify(title)
            if lang:
                new_filename = f"{slug}_{lang}.pdf"
            else:
                # Keep original name but clean it
                # Strip leading "NNN - " prefix if present
                clean = re.sub(r"^\d+\s*-\s*", "", old_filename)
                new_filename = clean if clean else old_filename

            # New directory: parent_dir/{work_folder}/
            new_dir = os.path.join(parent_dir, work_folder)
            new_path = os.path.join(new_dir, new_filename)

            print(f"  {'[dry]' if dry_run else 'MOVE'}: {old_filename}")
            print(f"         -> {work_folder}/{new_filename}")

            if not dry_run:
                try:
                    os.makedirs(new_dir, exist_ok=True)
                    shutil.move(old_path, new_path)
                    bf.stored_path = new_path
                    moved += 1
                except Exception as exc:
                    print(f"  ERRO: {exc}")
                    errors += 1
            else:
                moved += 1

        if not dry_run:
            db.commit()
            print(f"\nMigração concluída: {moved} movidos, {skipped} ignorados, {errors} erros.")
        else:
            print(f"\n[dry-run] Seria movidos: {moved}, ignorados: {skipped}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Migra PDFs para estrutura por obra")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    migrate(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
