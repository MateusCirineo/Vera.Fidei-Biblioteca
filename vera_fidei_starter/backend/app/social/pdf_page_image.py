"""Recorte de página real de PDF (PL/PG/PO) para os slides de citação do carrossel.

Usa o PDF que o próprio Vera.Fidei já tem na biblioteca (armazenamento local) —
não inventa nem busca a página em outro lugar.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path, PureWindowsPath

import pymupdf

from models.database import BookFile, SessionLocal


def _normalized_words(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return {word for word in re.findall(r"[a-z0-9]+", normalized) if len(word) >= 4}


def _book_file_path(book_file_id: int) -> Path | None:
    with SessionLocal() as db:
        book_file = db.get(BookFile, book_file_id)
    if book_file is None:
        return None
    return resolve_pdf_path(book_file.stored_path)


def resolve_pdf_path(stored_path: str) -> Path | None:
    """Resolve caminhos gravados tanto no Windows quanto no container Linux."""
    direct = Path(stored_path)
    if direct.is_file():
        return direct

    filename = PureWindowsPath(stored_path).name
    backend_dir = Path(__file__).resolve().parents[2]
    candidates = (
        backend_dir / "pdfs" / filename,
        Path("/app/pdfs") / filename,
    )
    return next((path for path in candidates if path.is_file()), None)


def render_pdf_page(book_file_id: int, pdf_page: int, dpi: int = 220) -> bytes | None:
    """Renderiza a página `pdf_page` (1-based, como mostrado no visualizador) do
    PDF de `book_file_id` como PNG. Devolve None se o arquivo não estiver
    disponível localmente (ex: armazenamento remoto) ou a página não existir."""
    path = _book_file_path(book_file_id)
    if path is None:
        return None

    with pymupdf.open(path) as doc:
        index = pdf_page - 1
        if index < 0 or index >= len(doc):
            return None
        page = doc[index]
        pix = page.get_pixmap(dpi=dpi)
        return pix.tobytes("png")


def render_pdf_title_page(
    book_file_id: int,
    *,
    author: str,
    work_title: str,
    dpi: int = 220,
) -> bytes | None:
    """Escolhe uma folha de rosto textual entre as primeiras páginas.

    Capas apenas gráficas e páginas de índice/apresentação não vencem a
    seleção. Isso evita ampliar uma capa inadequada no slide final.
    """
    path = _book_file_path(book_file_id)
    if path is None:
        return None
    expected = _normalized_words(f"{author} {work_title}")
    blocked = _normalized_words("índice sumário apresentação introdução bibliografia")
    with pymupdf.open(path) as doc:
        candidates: list[tuple[float, int]] = []
        for index in range(min(14, len(doc))):
            text = " ".join(doc[index].get_text("text").split())
            words = _normalized_words(text)
            # Uma folha de rosto é curta. Páginas introdutórias também podem
            # repetir autor/título, mas contêm dezenas de palavras corridas.
            if not words or len(words) > 60 or words & blocked:
                continue
            overlap = len(words & expected)
            if overlap < 2:
                continue
            score = overlap * 25 - max(0, len(words) - 40)
            candidates.append((score, index))
        if not candidates:
            # Muitas edições trazem a folha de rosto como imagem, sem camada
            # de texto. Entre as quatro primeiras páginas, aceitamos uma folha
            # clara com quantidade moderada de tinta; isso exclui capa colorida
            # sólida e página praticamente vazia.
            for index in range(min(4, len(doc))):
                text_words = _normalized_words(doc[index].get_text("text"))
                if len(text_words) > 10:
                    continue
                sample = doc[index].get_pixmap(
                    dpi=50, colorspace=pymupdf.csGRAY, alpha=False
                ).samples
                ink_ratio = sum(value < 235 for value in sample) / max(1, len(sample))
                if 0.005 <= ink_ratio <= 0.25:
                    candidates.append((10 - index - abs(ink_ratio - 0.04), index))
        if not candidates:
            return None
        _, index = max(candidates, key=lambda item: (item[0], -item[1]))
        return doc[index].get_pixmap(dpi=dpi).tobytes("png")


def render_pdf_quote_excerpts(
    book_file_id: int,
    pdf_page: int,
    quote: str,
    *,
    dpi: int = 240,
) -> list[bytes]:
    """Renderiza até dois blocos da página que efetivamente contêm a citação.

    Os blocos são encontrados por sobreposição de palavras normalizadas, para
    tolerar acentos e pequenas diferenças de OCR sem cortar palavras ao meio.
    """
    path = _book_file_path(book_file_id)
    if path is None:
        return []
    quote_words = _normalized_words(quote)
    if not quote_words:
        return []
    with pymupdf.open(path) as doc:
        index = pdf_page - 1
        if index < 0 or index >= len(doc):
            return []
        page = doc[index]
        scored: list[tuple[float, tuple]] = []
        for block in page.get_text("blocks"):
            text = str(block[4] or "")
            block_words = _normalized_words(text)
            if not block_words:
                continue
            shared = len(block_words & quote_words)
            score = shared / max(1, min(len(block_words), len(quote_words)))
            if shared >= 4 and score >= 0.12:
                scored.append((score, block))
        selected = sorted(
            (block for _, block in sorted(scored, key=lambda item: item[0], reverse=True)[:2]),
            key=lambda block: (block[1], block[0]),
        )
        rendered: list[bytes] = []
        for block in selected:
            clip = pymupdf.Rect(
                max(0, block[0] - 18),
                max(0, block[1] - 14),
                min(page.rect.width, block[2] + 18),
                min(page.rect.height, block[3] + 14),
            )
            rendered.append(page.get_pixmap(dpi=dpi, clip=clip).tobytes("png"))
        return rendered
