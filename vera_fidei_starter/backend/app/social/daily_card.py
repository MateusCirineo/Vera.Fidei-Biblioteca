"""Seleção rastreável de conteúdo para o Instagram do Vera.Fidei.

O Elasticsearch só sugere ``chunk_id``. Autor, obra, edição, citação e página
são reconstruídos do mesmo registro PostgreSQL antes de a arte ser gerada.
Isso impede o erro do protótipo que combinou uma frase de Santo Ambrósio com
nome, obra e imagem de Santo Agostinho.
"""

from __future__ import annotations

import datetime
import re
import textwrap
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.orm import joinedload

from app.social.content_guard import (
    extract_coherent_passage,
    is_manually_blocked,
    looks_like_editorial_noise,
    pick_highlight_terms,
    quote_fingerprint,
    same_author,
    validate_candidate,
)
from app.social.ledger import SocialLedger
from app.social.post_model import SocialPostCandidate
from core.config import settings
from models.database import Book, Chunk, SessionLocal
from search.text_search import AcervoSearchHit, TextSearchClient
from services.verification_service import _authoritative_source_text
from utils.author_detection import PATRISTIC_AUTHORS


BRAND_NAME = "Vera.Fidei"
BRAND_TAGLINE = "Biblioteca Católica Digital"
BRAND_FOOTER = "Fontes. Estudo. Rastreabilidade."
DailyCard = SocialPostCandidate

_AUTHOR_LIFE: dict[str, tuple[str, str]] = {
    "Santo Agostinho de Hipona": ("354–430", "séculos IV–V"),
    "Santo Ambrósio de Milão": ("340–397", "século IV"),
    "São Ambrósio de Milão": ("340–397", "século IV"),
    "São Jerônimo": ("c. 347–420", "séculos IV–V"),
    "São Gregório Magno": ("c. 540–604", "séculos VI–VII"),
    "São João Crisóstomo": ("c. 347–407", "séculos IV–V"),
    "Santo Ireneu de Lião": ("c. 130–c. 202", "séculos II–III"),
}


def _resolve_backend_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return Path(__file__).resolve().parents[2] / path


def _authors_with_content(db) -> list[str]:
    direct = {
        row[0]
        for row in db.query(Book.canonical_author)
        .filter(Book.canonical_author.isnot(None))
        .distinct()
        .all()
    }
    via_chunks = {
        row[0]
        for row in db.query(Chunk.chunk_author)
        .filter(Chunk.chunk_author.isnot(None))
        .distinct()
        .all()
    }
    return sorted((direct | via_chunks) & set(PATRISTIC_AUTHORS.keys()))


def pick_daily_author(day: int | None = None) -> str | None:
    day = day if day is not None else datetime.date.today().timetuple().tm_yday
    with SessionLocal() as db:
        authors = _authors_with_content(db)
    if not authors:
        return None
    return authors[day % len(authors)]


def _ordered_quality_hits(
    client: TextSearchClient, author: str, day: int
) -> list[AcervoSearchHit]:
    hits = client.author_chunks(author=author, limit=500)
    valid: list[tuple[int, AcervoSearchHit]] = []
    for hit in hits:
        raw = (hit.translation_text or hit.text or "").strip()
        passage = extract_coherent_passage(raw)
        if not passage or is_manually_blocked(passage):
            continue
        score = 0
        if hit.translation_text:
            score += 40
        if hit.pdf_page and hit.pdf_page > 8:
            score += 20
        if hit.work_title:
            score += 10
        if hit.edition_label or hit.collection:
            score += 10
        highlights = pick_highlight_terms(passage)
        score += len(highlights) * 18
        if len(highlights) < 2:
            score -= 45
        if re.search(r"\b(?:Ag|Ev)\.", passage):
            score -= 60
        if re.search(r"[A-Za-zÀ-ÿ]-\s+[a-zà-ÿ]", raw):
            score -= 20
        score -= abs(len(passage) - 700) // 20
        valid.append((score, hit))
    if not valid:
        return []
    valid.sort(key=lambda pair: (-pair[0], pair[1].chunk_id))
    # A data escolhe entre os melhores trechos, nunca entre todo o acervo.
    # Assim preservamos variedade sem permitir que um fragmento quebrado de
    # OCR vença apenas por causa do deslocamento diário.
    best_score = valid[0][0]
    shortlist = [pair for pair in valid if pair[0] >= best_score - 18][:30]
    offset = day % len(shortlist)
    rotated = shortlist[offset:] + shortlist[:offset]
    return [hit for _, hit in rotated]


def pick_daily_hit(
    client: TextSearchClient, author: str, day: int | None = None
) -> AcervoSearchHit | None:
    """Compatibilidade com ``/search/daily-citation``, já sem índices/TOC."""

    day = day if day is not None else datetime.date.today().timetuple().tm_yday
    hits = _ordered_quality_hits(client, author, day)
    return hits[0] if hits else None


def _pick_portuguese_text(chunk: Chunk, authoritative_text: str) -> tuple[str, str]:
    """Return only Portuguese wording proven by this exact PDF edition."""
    book_language = (chunk.book.language or "").lower()
    if book_language in {"pt", "pt-br", "português", "portugues"}:
        return authoritative_text.strip(), ""

    # Legacy translations have no independent edition/page proof yet.
    return "", ""


def _candidate_from_hit(
    hit: AcervoSearchHit, *, expected_author: str, day: int
) -> SocialPostCandidate | None:
    with SessionLocal() as db:
        chunk = (
            db.query(Chunk)
            .options(
                joinedload(Chunk.book),
                joinedload(Chunk.source_file),
            )
            .filter(Chunk.id == hit.chunk_id)
            .first()
        )
        if chunk is None or chunk.book is None:
            return None

        authoritative = _authoritative_source_text(db, chunk, "", chunk.text)
        if authoritative is None:
            return None
        authoritative_text, _source_fidelity = authoritative

        book = chunk.book
        author = (book.canonical_author or chunk.chunk_author or book.author or "").strip()
        if not same_author(expected_author, author):
            return None
        full_text, translation_edition = _pick_portuguese_text(chunk, authoritative_text)
        passage = extract_coherent_passage(full_text)
        if not passage or looks_like_editorial_noise(passage):
            return None

        work_title = (book.canonical_title or book.title or hit.work_title or "").strip()
        work_title = re.sub(r"^Patrística\s+Vol\.\s*\d+(?:_\d+)?\s*[—-]\s*", "", work_title, flags=re.I)
        edition = (translation_edition or book.edition_label or hit.edition_label or "").strip() or None
        source_file = chunk.source_file
        dates, century = _AUTHOR_LIFE.get(author, (None, None))

        candidate = SocialPostCandidate(
            chunk_id=chunk.id,
            book_id=book.id,
            book_file_id=chunk.book_file_id,
            author=author,
            work_title=work_title,
            quote=passage,
            original_text=authoritative_text.strip(),
            language=(book.language or hit.language or "").strip(),
            collection=(book.collection or hit.collection or "").strip() or None,
            volume=chunk.volume or book.volume_number or hit.volume,
            edition_label=edition,
            chapter_or_section=(chunk.chapter_or_section or hit.chapter_or_section or "").strip() or None,
            pdf_page=chunk.pdf_page or hit.pdf_page,
            column_start=chunk.column_start or None,
            column_end=chunk.column_end or None,
            stored_path=(source_file.stored_path if source_file else None),
            author_dates=dates,
            century=century,
            day_of_year=day,
            highlight_terms=pick_highlight_terms(passage),
        )
        candidate.source_fingerprint = quote_fingerprint(
            chunk_id=candidate.chunk_id,
            author=candidate.author,
            work_title=candidate.work_title,
            quote=candidate.quote,
        )
        return candidate


def pick_daily_card(
    day: int | None = None,
    author: str | None = None,
    *,
    ledger: SocialLedger | None = None,
) -> DailyCard | None:
    day = day if day is not None else datetime.date.today().timetuple().tm_yday
    author = author or pick_daily_author(day)
    if not author:
        return None

    if ledger is None:
        ledger = SocialLedger(_resolve_backend_path(settings.social_ledger_path))
    published = ledger.published_fingerprints()
    client = TextSearchClient()
    for hit in _ordered_quality_hits(client, author, day):
        candidate = _candidate_from_hit(hit, expected_author=author, day=day)
        if candidate is None:
            continue
        report = validate_candidate(
            candidate,
            expected_author=author,
            published_fingerprints=published,
        )
        if report.ok:
            return candidate
    return None


def format_reference(card: DailyCard) -> str:
    author = card.author
    if card.author_dates:
        author += f" ({card.author_dates})"
    if card.century:
        author += f", {card.century}"

    source_bits: list[str] = [card.work_title]
    if card.chapter_or_section:
        source_bits.append(card.chapter_or_section)
    if card.collection and card.volume:
        source_bits.append(f"{card.collection} {card.volume}")
    elif card.collection:
        source_bits.append(card.collection)
    if card.collection in {"PL", "PG", "PO"} and card.column_start:
        columns = str(card.column_start)
        if card.column_end and card.column_end != card.column_start:
            columns += f"–{card.column_end}"
        source_bits.append(f"cols. {columns}")
    if card.pdf_page:
        source_bits.append(f"p. {card.pdf_page}")
    if card.edition_label:
        source_bits.append(card.edition_label)
    return f"{author}; " + ", ".join(bit for bit in source_bits if bit) + "."


def build_caption(card: DailyCard) -> str:
    topics = ", ".join(card.highlight_terms[:4])
    opening = (
        "Hoje voltamos diretamente às fontes da Era Patrística. "
        f"{card.author}"
    )
    if card.century:
        opening += f", autor dos {card.century},"
    opening += f" é apresentado aqui por meio de sua obra {card.work_title}."
    topic_line = (
        f"Neste trecho, aparecem temas como {topics}."
        if topics
        else "O trecho abaixo foi selecionado diretamente da edição conservada no acervo."
    )
    return "\n".join(
        [
            opening,
            "",
            topic_line,
            "",
            card.quote,
            "",
            format_reference(card),
            "",
            "Trecho conferido no acervo Vera.Fidei. Autor, obra, edição e página permanecem ligados à mesma fonte; a imagem inferior da arte reproduz o trecho da página utilizada.",
            "",
            BRAND_FOOTER,
            "",
            "#PadresDaIgreja #Patrística #Católico #Teologia #VeraFidei #FéCatólica #Apologética",
        ]
    )


# Renderizador quadrado legado. O fluxo novo usa ``carousel.render_carousel``.
def _load_font(candidates: list[str], size: int) -> ImageFont.ImageFont:
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render_quote_card(card: DailyCard) -> bytes:
    size = (1080, 1080)
    image = Image.new("RGB", size, (17, 17, 26))
    draw = ImageDraw.Draw(image)
    font = _load_font([settings.social_body_font_path, "C:/Windows/Fonts/arial.ttf"], 38)
    lines = textwrap.wrap(card.quote, width=42)[:15]
    y = 110
    for line in lines:
        draw.text((80, y), line, font=font, fill=(240, 235, 220))
        y += 55
    draw.text((80, 930), format_reference(card), font=_load_font(["C:/Windows/Fonts/georgia.ttf"], 24), fill=(198, 161, 91))
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()
