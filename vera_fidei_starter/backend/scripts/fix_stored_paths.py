"""
Migra stored_path absolutos (Windows ou Linux) para paths relativos à pasta pdfs/.

Rodar no servidor após o rsync dos PDFs:
    docker exec -it vera_fidei_starter-backend-1 python scripts/fix_stored_paths.py

Ou localmente (dev):
    python backend/scripts/fix_stored_paths.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Garante que o diretório backend está no sys.path quando rodado como script
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from models.database import BookFile, SessionLocal, init_db  # noqa: E402

PDF_ROOT_BASE = BACKEND_DIR / "pdfs"

# Em Docker usa /app/pdfs; fora usa a pasta local
PDFS_DIR = Path(os.environ.get("PDF_DIR") or PDF_ROOT_BASE)


def _find_relative_path(stored_path: str) -> str | None:
    """
    Tenta localizar o arquivo no disco e retorna o path relativo a PDFS_DIR.
    Retorna None se não encontrar.
    """
    normalized = stored_path.replace("\\", "/")
    basename = normalized.split("/")[-1]
    if not basename:
        return None

    # Já é relativo e o arquivo existe — não precisa migrar
    if not os.path.isabs(stored_path.replace("\\", "/").replace("\\", "/")):
        if (PDFS_DIR / stored_path.replace("\\", "/")).is_file():
            return stored_path.replace("\\", "/")

    # Busca recursiva pelo basename dentro de PDFS_DIR
    for root, _dirs, files in os.walk(PDFS_DIR):
        for f in files:
            if f == basename:
                rel = os.path.relpath(os.path.join(root, f), PDFS_DIR)
                return rel.replace("\\", "/")

    return None


def main() -> None:
    init_db(reset=False)

    stats = {"checked": 0, "fixed": 0, "already_relative": 0, "not_found": 0}

    with SessionLocal() as db:
        book_files = db.query(BookFile).all()
        stats["checked"] = len(book_files)

        for bf in book_files:
            if not bf.stored_path:
                continue

            normalized = bf.stored_path.replace("\\", "/")

            # Já é path relativo curto e correto — pula
            if not os.path.isabs(normalized) and not normalized.startswith("/"):
                # Verifica se o arquivo existe com esse path relativo
                if (PDFS_DIR / normalized).is_file():
                    stats["already_relative"] += 1
                    continue

            # Tenta encontrar o arquivo no disco e obter path relativo
            new_path = _find_relative_path(bf.stored_path)

            if new_path is None:
                stats["not_found"] += 1
                print(f"  NAO_ENCONTRADO book_file_id={bf.id} original={bf.stored_path!r}")
                continue

            if new_path != bf.stored_path:
                print(f"  CORRIGINDO book_file_id={bf.id}")
                print(f"    antes: {bf.stored_path!r}")
                print(f"    depois: {new_path!r}")
                bf.stored_path = new_path
                stats["fixed"] += 1
            else:
                stats["already_relative"] += 1

        db.commit()

    print(
        f"\nDONE checked={stats['checked']} "
        f"fixed={stats['fixed']} "
        f"already_ok={stats['already_relative']} "
        f"not_found={stats['not_found']}"
    )


if __name__ == "__main__":
    main()
