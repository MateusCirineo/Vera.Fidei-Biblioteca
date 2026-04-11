"""Utilitários de idioma compartilhados entre backend e serviços."""

from __future__ import annotations

import re as _re

# Normalização de nomes de língua para ISO 639-1/639-3
LANGUAGE_NORMALIZE: dict[str, str] = {
    "latim": "la", "latin": "la",
    "grego": "grc", "greek": "grc", "grego antigo": "grc", "ancient greek": "grc",
    "hebraico": "he", "hebrew": "he",
    "siríaco": "syc", "syriac": "syc",
    "copta": "cop", "coptic": "cop",
    "árabe": "ar", "arabic": "ar",
    "etíope": "gez", "ethiopic": "gez", "ge'ez": "gez",
    "português": "pt", "portuguese": "pt",
    "espanhol": "es", "spanish": "es",
    "alemão": "de", "german": "de",
    "inglês": "en", "english": "en",
    "francês": "fr", "french": "fr",
    "italiano": "it", "italian": "it",
}

# Grupos de idioma para roteamento de busca e classificação
ORIGINAL_LANGS: frozenset[str] = frozenset({"la", "grc", "el", "he", "syc", "cop", "ar", "gez"})
TRANSLATION_LANGS: frozenset[str] = frozenset({"pt", "es", "fr", "it", "en", "de"})
ORIENTAL_LANGS: frozenset[str] = frozenset({"syc", "cop", "ar", "gez", "he"})

# Regras de coleção → tradição patrística
COLLECTION_TO_TRADITION: dict[str, str] = {
    "PG": "grega",
    "PO": "oriental",
    "PL": "latina",
}

# Regras de coleção → seção da biblioteca
COLLECTION_DOCUMENT_SECTIONS: frozenset[str] = frozenset({"CONC", "MAG"})

# Tipo de documento por coleção
COLLECTION_TO_DOCTYPE: dict[str, str] = {
    "CONC": "concilio",
    "MAG": "outro",
}


# ─── Latin heuristic ─────────────────────────────────────────────────────────

LATIN_WORD_MARKERS: frozenset[str] = frozenset({
    "est", "non", "sed", "qui", "quod", "cum", "per", "ad", "ut", "enim",
    "autem", "etiam", "iam", "nunc", "sibi", "ipse", "esse", "erat", "ergo",
    "sanctus", "ecclesia", "deus", "dominus", "christus", "spiritus",
    "pater", "filius", "verbum", "gratia", "salus", "fides",
})
LATIN_PROPORTION_THRESHOLD = 0.08   # 8% dos tokens = latim
LATIN_ABSOLUTE_MIN = 4              # pelo menos 4 marcadores, independente da proporção


def detect_latin_heuristic(text: str) -> bool:
    """
    Retorna True se o texto provavelmente é Latim clássico.
    Usa proporção de tokens-marcadores, não contagem simples.
    Remove pontuação antes de tokenizar para evitar falsos negativos.
    """
    clean = _re.sub(r"[^\w\s]", " ", text.lower())
    tokens = [t for t in clean.split() if len(t) > 1]
    if not tokens:
        return False
    markers_found = sum(1 for t in tokens if t in LATIN_WORD_MARKERS)
    proportion = markers_found / len(tokens)
    return markers_found >= LATIN_ABSOLUTE_MIN and proportion >= LATIN_PROPORTION_THRESHOLD


def normalize_lang(raw: str) -> str:
    """Converte nome de língua em texto livre para ISO 639-1/639-3."""
    return LANGUAGE_NORMALIZE.get(raw.strip().lower(), raw.strip().lower())


def classify_book(
    collection: str,
    language: str,
    is_primary_source: bool,
) -> tuple[str, str | None, str | None]:
    """
    Classifica automaticamente um livro na estrutura da biblioteca.

    Retorna: (library_section, patristic_tradition, document_type)

    library_section:       "patristica" | "documentos"
    patristic_tradition:   "grega" | "oriental" | "latina" | "portuguesa" | None
    document_type:         "concilio" | "bula" | "enciclica" |
                           "constituicao_apostolica" | "carta_apostolica" | "outro" | None

    Regras:
      - Coleções CONC / MAG → documentos da Igreja
      - Tradução ou idioma vernáculo → patrística em português
      - PG ou língua grega → patrística grega
      - PO ou língua oriental → patrística oriental
      - Resto → patrística latina (PL e afins)
    """
    coll = collection.upper().strip()
    lang_iso = normalize_lang(language)

    # Documentos da Igreja
    if coll in COLLECTION_DOCUMENT_SECTIONS:
        return "documentos", None, COLLECTION_TO_DOCTYPE.get(coll, "outro")

    # Tradução / vernáculo → Patrística em Português
    if not is_primary_source or lang_iso in TRANSLATION_LANGS:
        return "patristica", "portuguesa", None

    # Patrística Grega
    if coll == "PG" or lang_iso in ("grc", "el"):
        return "patristica", "grega", None

    # Patrística Oriental
    if coll == "PO" or lang_iso in ORIENTAL_LANGS:
        return "patristica", "oriental", None

    # Patrística Latina (PL ou padrão)
    return "patristica", "latina", None
