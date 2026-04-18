"""
Detecta o autor individual de cada chunk nos volumes coletânea (multi-autor)
e persiste o resultado em Chunk.chunk_author + atualiza os índices ES e ChromaDB.

Volumes alvo:
  Book 9 — Vol. 1 Padres Apostólicos
  Book 7 — Vol. 2 Padres Apologistas

Estratégia:
  1. Abre o PDF com pdfplumber.
  2. Varre cada página procurando por cabeçalhos de seção de autor.
  3. Constrói mapa {pdf_page: author_name}.
  4. Atualiza Chunk.chunk_author em todos os chunks cujo pdf_page bate no mapa.
  5. Re-indexa no Elasticsearch (update parcial do campo "author").
  6. Atualiza metadados no ChromaDB.

Idempotente: pode ser executado múltiplas vezes sem efeito colateral.

Execução:
  cd vera_fidei_starter/backend
  python -m scripts.tag_chunk_authors
"""

from __future__ import annotations

import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pdfplumber
from models.database import SessionLocal, Book, Chunk, init_db

# ─── Tabela de padrões por volume ────────────────────────────────────────────
#
# Cada entrada: (regex_normalizado, canonical_author)
# O regex é testado contra o texto NORMALIZADO da página (sem acentos, lowercase).
# A ordem importa: padrões mais específicos primeiro.

VOL1_PATTERNS: list[tuple[str, str]] = [
    # Clemente Romano — só reconhece como header quando o nome é o cabeçalho da página
    (r"^clemente\s+romano$",                "São Clemente de Roma"),
    (r"^clemente\s+romano\s",               "São Clemente de Roma"),
    (r"^primeira\s+carta\s+de\s+clemente",  "São Clemente de Roma"),
    (r"^carta\s+aos\s+corintios$",          "São Clemente de Roma"),
    # Inácio de Antioquia
    (r"^inacio\s+de\s+antioquia",           "Santo Inácio de Antioquia"),
    (r"^ignacio\s+de\s+antioquia",          "Santo Inácio de Antioquia"),
    # Policarpo de Esmirna
    (r"^policarpo\s+de\s+esmirna",          "São Policarpo de Esmirna"),
    (r"^policarpo\s+de\s+esmirna$",         "São Policarpo de Esmirna"),
    # Hermas
    (r"^hermas$",                            "Hermas"),
    (r"^o\s+pastor\s+de\s+hermas",          "Hermas"),
    (r"^pastor\s+de\s+hermas",              "Hermas"),
    # Barnabé
    (r"^carta\s+de\s+barnabe",              "São Barnabé"),
    (r"^barnabe$",                           "São Barnabé"),
    (r"^epistola\s+de\s+barnabe",           "São Barnabé"),
    # Papias
    (r"^papias\s+de\s+hierapolis",          "Papias de Hierápolis"),
    (r"^papias$",                            "Papias de Hierápolis"),
    # Didaqué
    (r"^didaque",                            "Didaqué"),
    (r"^didache",                            "Didaqué"),
    (r"^doutrina\s+dos\s+doze",             "Didaqué"),
]

VOL2_PATTERNS: list[tuple[str, str]] = [
    # Carta a Diogneto
    (r"^carta\s+a\s+diogneto",              "Carta a Diogneto"),
    (r"^diogneto$",                          "Carta a Diogneto"),
    # Aristides
    (r"^aristides\s+de\s+atenas",           "Aristides de Atenas"),
    (r"^aristides$",                         "Aristides de Atenas"),
    # Taciano
    (r"^taciano",                            "Taciano, o Sírio"),
    (r"^oracao\s+aos\s+gregos",             "Taciano, o Sírio"),
    # Teófilo de Antioquia
    (r"^teofilo\s+de\s+antioquia",          "Teófilo de Antioquia"),
    (r"^teofilo$",                           "Teófilo de Antioquia"),
    # Atenágoras
    (r"^atenagoras",                         "Atenágoras de Atenas"),
    (r"^legacao\s+pelos\s+cristaos",        "Atenágoras de Atenas"),
    # Hermias
    (r"^hermias",                            "Hermias"),
]

# PG Vol. 1 — Patrologia Graeca, Migne (texto em latim extraído por OCR)
# Contém: Barnabé, Clemente Romano, Hermas, Inácio de Antioquia, Policarpo, Papias
PG_VOL1_PATTERNS: list[tuple[str, str]] = [
    # ── Clemente Romano ──────────────────────────────────────────────
    # Latim (Migne)
    (r"^s\.?\s*clementis\s+i\b",                "São Clemente de Roma"),
    (r"^clementis\s+romani",                     "São Clemente de Roma"),
    (r"^epistola\s+(i\s+)?clementis",            "São Clemente de Roma"),
    # Grego transliterado pelo OCR (Κλήμης → Klemes/Klemens)
    (r"^kleme(n|nt)s",                           "São Clemente de Roma"),
    (r"^klhm",                                   "São Clemente de Roma"),

    # ── Inácio de Antioquia ──────────────────────────────────────────
    # Latim
    (r"^s\.?\s*ignatii\s+antiocheni",            "Santo Inácio de Antioquia"),
    (r"^ignatii\s+antiocheni",                   "Santo Inácio de Antioquia"),
    (r"^sancti\s+ignatii",                       "Santo Inácio de Antioquia"),
    (r"^epistolae\s+ignatii",                    "Santo Inácio de Antioquia"),
    # Grego transliterado (Ἰγνάτιος → Ignatios/Ignatius)
    (r"^ignatios",                               "Santo Inácio de Antioquia"),
    (r"^igna(t|th)ios",                          "Santo Inácio de Antioquia"),

    # ── Policarpo de Esmirna ─────────────────────────────────────────
    # Latim
    (r"^s\.?\s*polycarpi\s+smyrnensis",          "São Policarpo de Esmirna"),
    (r"^polycarpi\s+smyrnensis",                 "São Policarpo de Esmirna"),
    (r"^epistola\s+polycarpi",                   "São Policarpo de Esmirna"),
    (r"^martyrium\s+polycarpi",                  "São Policarpo de Esmirna"),
    # Grego transliterado (Πολύκαρπος → Polykarpos)
    (r"^polykarpos",                             "São Policarpo de Esmirna"),
    (r"^polykarpo(s|u)",                         "São Policarpo de Esmirna"),

    # ── Hermas ───────────────────────────────────────────────────────
    # Latim
    (r"^hermae\s+pastor",                        "Hermas"),
    (r"^pastor\s+hermae",                        "Hermas"),
    # Grego transliterado (Ἑρμᾶς → Hermas / Poimen)
    (r"^hermas$",                                "Hermas"),
    (r"^poimen\s+(tou\s+)?herma",                "Hermas"),

    # ── Barnabé ──────────────────────────────────────────────────────
    # Latim
    (r"^barnabae\s+apostoli",                    "São Barnabé"),
    (r"^epistola\s+barnabae",                    "São Barnabé"),
    (r"^s\.?\s*barnabae",                        "São Barnabé"),
    # Grego transliterado (Βαρνάβας → Barnabas)
    (r"^barnabas$",                              "São Barnabé"),
    (r"^epistole\s+barnaba",                     "São Barnabé"),

    # ── Papias ───────────────────────────────────────────────────────
    # Latim
    (r"^papiae\s+(fragmenta|hieropolitani)",     "Papias de Hierápolis"),
    # Grego transliterado (Παπίας → Papias)
    (r"^papias",                                 "Papias de Hierápolis"),

    # ── Didaqué ──────────────────────────────────────────────────────
    # Latim
    (r"^doctrina\s+(duodecim|apostolorum)",      "Didaqué"),
    # Grego transliterado (Διδαχή → Didache)
    (r"^didache",                                "Didaqué"),
    (r"^didakhe",                                "Didaqué"),
]

# Book ID → (PDF stored_path suffix pattern, patterns list)
COLLECTANEA_BOOKS: dict[int, tuple[str, list]] = {
    9:  ("Vol._1",  VOL1_PATTERNS),
    7:  ("Vol._2",  VOL2_PATTERNS),
    25: ("PG001",   PG_VOL1_PATTERNS),
}


def _norm(text: str) -> str:
    """Remove acentos, lowercase, colapsa espaços."""
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", text).strip()


def scan_pdf_sections(pdf_path: str, patterns: list[tuple[str, str]]) -> dict[int, str]:
    """
    Varre o PDF e retorna {pdf_page_number: author_name}.

    Estratégia de detecção: só detecta mudança de seção quando o padrão
    aparece nas PRIMEIRAS LINHAS da página (cabeçalho de seção), e não em
    qualquer parte do texto. Isso evita que menções ao autor no corpo do
    texto ou no índice mudem o autor atribuído.

    A lógica é "sticky": uma vez detectado um autor, ele continua até o
    próximo cabeçalho de seção.
    """
    page_map: dict[int, str] = {}
    current_author: str | None = None

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            raw_text = page.extract_text() or ""

            # Usa apenas a PRIMEIRA linha não vazia para detecção de header de seção.
            # Isso evita que menções ao autor no corpo do texto ou no rodapé
            # mudem o autor atribuído (e.g., "Pseudo-Barnabé" em nota de rodapé).
            lines = [ln.strip() for ln in raw_text.split('\n') if ln.strip()]
            first_line = lines[0] if lines else ""
            header_norm = _norm(first_line)

            # Tenta detectar novo header de seção nesta página
            for pattern, author in patterns:
                if re.search(pattern, header_norm):
                    current_author = author
                    break  # usa o primeiro match (patterns ordenados por especificidade)

            if current_author:
                page_map[i] = current_author

    return page_map


def find_pdf_path(book: Book) -> str | None:
    """Encontra o caminho do PDF associado ao livro."""
    for f in book.files:
        if f.stored_path and os.path.exists(f.stored_path):
            return f.stored_path
    # Fallback: busca na pasta pdfs/ pelo padrão do nome do arquivo
    pdfs_dir = os.path.join(os.path.dirname(__file__), "..", "pdfs")
    prefix = f"{book.id}_"
    for fname in os.listdir(pdfs_dir):
        if fname.startswith(prefix):
            return os.path.join(pdfs_dir, fname)
    return None


def update_elasticsearch(chunk_id: int, author: str) -> None:
    """Atualiza o campo 'author' do documento ES do chunk."""
    try:
        from search.text_search import TextSearchClient, ES_INDEX
        client = TextSearchClient()
        client.es.update(index=ES_INDEX, id=str(chunk_id), doc={"author": author})
    except Exception as exc:
        print(f"  [ES] aviso: chunk {chunk_id} não atualizado — {exc}")


def update_chromadb(chunk_id: int, author: str) -> None:
    """Atualiza o metadado 'author' no ChromaDB."""
    try:
        from search.semantic_search import SemanticSearchClient
        client = SemanticSearchClient()
        # ChromaDB.update só aceita os campos que existem no documento
        existing = client.collection.get(ids=[str(chunk_id)], include=["metadatas"])
        if existing and existing["metadatas"]:
            meta = {**existing["metadatas"][0], "author": author}
            client.collection.update(ids=[str(chunk_id)], metadatas=[meta])
    except Exception as exc:
        print(f"  [ChromaDB] aviso: chunk {chunk_id} não atualizado — {exc}")


def tag_book(book_id: int, patterns: list, db, dry_run: bool = False) -> int:
    """Processa um livro coletânea. Retorna número de chunks marcados."""
    book = db.get(Book, book_id)
    if book is None:
        print(f"  ERRO: book_id={book_id} não encontrado no banco.")
        return 0

    pdf_path = find_pdf_path(book)
    if not pdf_path:
        print(f"  ERRO: PDF do book_id={book_id} não encontrado.")
        return 0

    print(f"\n  Livro: [{book_id}] {book.title}")
    print(f"  PDF:   {pdf_path}")

    page_map = scan_pdf_sections(pdf_path, patterns)
    author_counts: dict[str, int] = {}
    for author in page_map.values():
        author_counts[author] = author_counts.get(author, 0) + 1

    print(f"  Seções detectadas no PDF ({len(page_map)} páginas mapeadas):")
    for author, count in sorted(author_counts.items()):
        print(f"    · {author}: {count} páginas")

    if not page_map:
        print("  AVISO: nenhuma seção detectada — verifique os padrões.")
        return 0

    chunks = db.query(Chunk).filter(Chunk.book_id == book_id).all()
    tagged = 0
    for chunk in chunks:
        author = page_map.get(chunk.pdf_page)  # None se página não mapeada
        if chunk.chunk_author == author:
            continue  # já correto, idempotente

        if not dry_run:
            chunk.chunk_author = author
            if author:
                update_elasticsearch(chunk.id, author)
                update_chromadb(chunk.id, author)
        tagged += 1

    if not dry_run:
        db.commit()

    print(f"  {'[DRY RUN] ' if dry_run else ''}Chunks marcados: {tagged}/{len(chunks)}")
    return tagged


def main(dry_run: bool = False) -> None:
    init_db()  # garante que a coluna chunk_author existe antes de prosseguir

    print("=" * 60)
    print("tag_chunk_authors — atribuição de autores nos volumes coletânea")
    if dry_run:
        print("MODO DRY RUN: nenhuma alteração será salva")
    print("=" * 60)

    total = 0
    with SessionLocal() as db:
        for book_id, (_, patterns) in COLLECTANEA_BOOKS.items():
            total += tag_book(book_id, patterns, db, dry_run=dry_run)

    print(f"\nTotal de chunks marcados: {total}")
    print("Concluído.")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    main(dry_run=dry)
