"""
Importa todos os PDFs de uma pasta para a biblioteca Vera.Fidei.

Uso:
    python -m scripts.import_folder <caminho_da_pasta> [--api http://localhost:8000]

Exemplo:
    python -m scripts.import_folder "C:/PDFs/Patrologia Grega"
    python -m scripts.import_folder ../../../pdfs_entrada

O script:
  - Lê todos os arquivos .pdf da pasta (não recursivo por padrão)
  - Chama POST /books/ingest-auto para cada um
  - O backend detecta automaticamente: autor, título, coleção, idioma
  - Exibe progresso em tempo real
  - PDFs que já foram importados são ignorados (409 Conflict)
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import requests


def import_folder(folder: str, api: str, recursive: bool = False) -> None:
    folder = os.path.abspath(folder)
    if not os.path.isdir(folder):
        print(f"[ERRO] Pasta não encontrada: {folder}")
        sys.exit(1)

    # Coletar PDFs
    pdf_files: list[str] = []
    if recursive:
        for root, _, files in os.walk(folder):
            for f in files:
                if f.lower().endswith(".pdf"):
                    pdf_files.append(os.path.join(root, f))
    else:
        pdf_files = [
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if f.lower().endswith(".pdf")
        ]

    pdf_files.sort()

    if not pdf_files:
        print(f"Nenhum PDF encontrado em: {folder}")
        return

    print(f"\n{len(pdf_files)} PDF(s) encontrado(s) em: {folder}\n")
    print("-" * 60)

    ok = err = skipped = 0

    for i, path in enumerate(pdf_files, start=1):
        filename = os.path.basename(path)
        print(f"[{i}/{len(pdf_files)}] {filename}", end=" ... ", flush=True)

        try:
            with open(path, "rb") as f:
                res = requests.post(
                    f"{api}/books/ingest-auto",
                    files={"file": (filename, f, "application/pdf")},
                    timeout=60,
                )

            if res.status_code == 201:
                data = res.json()
                author = data.get("canonical_author") or data.get("author", "?")
                title = data.get("title", "?")
                book_id = data.get("id")
                print(f"OK  ->  {author} / {title}  (id={book_id}, indexando em background)")
                ok += 1

            elif res.status_code == 409:
                print("ignorado (já existe)")
                skipped += 1

            else:
                print(f"ERRO {res.status_code}: {res.text[:120]}")
                err += 1

        except requests.exceptions.ConnectionError:
            print(f"ERRO: backend não está respondendo em {api}")
            err += 1

        except Exception as exc:
            print(f"ERRO: {exc}")
            err += 1

        # Pequena pausa para não sobrecarregar o backend com OCR em paralelo
        if i < len(pdf_files):
            time.sleep(0.5)

    print("-" * 60)
    print(f"\nConcluído: {ok} importado(s), {skipped} ignorado(s), {err} erro(s)\n")
    if ok > 0:
        print("Os PDFs estão sendo indexados em background pelo backend.")
        print(f"Consulte: GET {api}/books/{{id}}/status para acompanhar.\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Importa PDFs de uma pasta para a biblioteca Vera.Fidei."
    )
    parser.add_argument("folder", help="Caminho da pasta com os PDFs")
    parser.add_argument(
        "--api",
        default="http://localhost:8000",
        help="URL base do backend (padrão: http://localhost:8000)",
    )
    parser.add_argument(
        "--recursive", "-r",
        action="store_true",
        help="Busca PDFs em subpastas também",
    )
    args = parser.parse_args()
    import_folder(args.folder, args.api.rstrip("/"), args.recursive)


if __name__ == "__main__":
    main()
