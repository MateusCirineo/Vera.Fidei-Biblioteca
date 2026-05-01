"""
Desfaz o aninhamento extra criado pela migração nos arquivos de documentos_pontificios.

Padrão errado:  .../Year - Title/Title/Title - LANG.pdf
Padrão correto: .../Year - Title/Title - LANG.pdf

Executa:
  cd vera_fidei_starter/backend
  python scripts/fix_pontificios_nesting.py [--dry-run]
"""
from __future__ import annotations
import argparse
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def fix(dry_run: bool = False) -> None:
    from models.database import SessionLocal, BookFile

    with SessionLocal() as db:
        files = db.query(BookFile).filter(
            BookFile.stored_path.contains("documentos_pontificios")
        ).all()

        moved = skipped = errors = 0

        for bf in files:
            old_path = os.path.normpath(bf.stored_path)
            if not os.path.isfile(old_path):
                skipped += 1
                continue

            parts = old_path.split(os.sep)
            fname = parts[-1]       # "Maximum Illud - DE.pdf"
            extra_folder = parts[-2]  # "Maximum Illud"  ← extra level
            year_folder = parts[-3] if len(parts) > 3 else ""  # "1919 - Maximum Illud"

            # Only fix if extra_folder appears inside year_folder (pattern "Year - Title")
            if not (" - " in year_folder and extra_folder in year_folder):
                skipped += 1
                continue

            # New path: remove the extra_folder level
            new_path = os.path.join(os.sep.join(parts[:-2]), fname)

            if old_path == new_path:
                skipped += 1
                continue

            print(f"  {'[dry]' if dry_run else 'FIX'}: ...{old_path[-80:]}")
            print(f"         to: ...{new_path[-60:]}")

            if not dry_run:
                try:
                    os.makedirs(os.path.dirname(new_path), exist_ok=True)
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
            # Clean up empty extra folders
            _cleanup_empty_dirs(files)
            print(f"\nConcluido: {moved} corrigidos, {skipped} ignorados, {errors} erros.")
        else:
            print(f"\n[dry-run] Seria corrigidos: {moved}, ignorados: {skipped}")


def _cleanup_empty_dirs(files) -> None:
    """Remove empty directories left after moving files."""
    dirs_checked = set()
    for bf in files:
        d = os.path.dirname(os.path.normpath(bf.stored_path))
        # Check one level up for empty dirs
        parent = os.path.dirname(d)
        dirs_checked.add(parent)

    for d in dirs_checked:
        try:
            for item in os.listdir(d):
                subdir = os.path.join(d, item)
                if os.path.isdir(subdir) and not os.listdir(subdir):
                    os.rmdir(subdir)
        except Exception:
            pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    fix(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
