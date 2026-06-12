"""Utilitários de idioma compartilhados entre backend e serviços."""

from __future__ import annotations

import re as _re

# Normalização de nomes de língua para ISO 639-1/639-3
LANGUAGE_NORMALIZE: dict[str, str] = {
    "la": "la", "lat": "la",
    "grc": "grc", "el": "grc",
    "pt": "pt", "por": "pt",
    "es": "es", "spa": "es",
    "en": "en", "eng": "en",
    "fr": "fr", "fra": "fr", "fre": "fr",
    "it": "it", "ita": "it",
    "de": "de", "ger": "de", "deu": "de",
    "he": "he", "heb": "he",
    "syc": "syc",
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
COLLECTION_DOCUMENT_SECTIONS: frozenset[str] = frozenset({
    "CONC", "MAG", "CIC", "CDC", "CCEO", "DZ",
})

# Tipo de documento por coleção
COLLECTION_TO_DOCTYPE: dict[str, str] = {
    "CONC": "concilio",
    "MAG": "outro",
    "CIC": "catecismo",        # CIC = Catecismo da Igreja Católica
    "CDC": "direito_canonico", # CDC = Código de Direito Canônico
    "CCEO": "direito_canonico",
    "DZ": "outro",
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
    normalized = raw.strip().lower()
    if not normalized:
        return normalized

    parts = [
        part.strip()
        for segment in _re.sub(r"\s+e\s+", "/", normalized).split("/")
        for part in _re.split(r"[+,;|]", segment)
        if part.strip()
    ]

    if len(parts) > 1:
        labels: list[str] = []
        for part in parts:
            label = LANGUAGE_NORMALIZE.get(part, part)
            if label not in labels:
                labels.append(label)
        return "+".join(labels)

    return LANGUAGE_NORMALIZE.get(normalized, normalized)


# ─── Script detection by Unicode block ───────────────────────────────────────

# (lo, hi inclusive, iso_code)
_SCRIPT_RANGES: list[tuple[int, int, str]] = [
    (0x0370, 0x03D6, "grc"),   # Grego básico (α–ω, Α–Ω, etc.)
    (0x1F00, 0x1FFF, "grc"),   # Grego Extendido (polítonico)
    (0x0700, 0x074F, "syc"),   # Siríaco
    (0x2C80, 0x2CFF, "cop"),   # Copta
    (0x03E2, 0x03EF, "cop"),   # Copta (letras no bloco Grego)
    (0x0530, 0x058F, "hy"),    # Armênio
    (0x10D0, 0x10FF, "ka"),    # Georgiano (Mkhedruli)
    (0x1200, 0x137F, "gez"),   # Etíope (Ge'ez)
    (0x0590, 0x05FF, "he"),    # Hebraico
    (0x0600, 0x06FF, "ar"),    # Árabe
]


def detect_script_heuristic(text: str) -> str | None:
    """
    Detecta o script de um texto a partir de blocos Unicode.
    Analisa os primeiros 300 caracteres e retorna o código ISO do script dominante,
    ou None se nenhum script não-latino for detectado com confiança (≥ 3 chars).

    Útil para queries em grego polítonico, siríaco, copta, armênio, árabe, etc.
    onde langdetect falha ou retorna resultados incorretos.
    """
    counts: dict[str, int] = {}
    for ch in text[:300]:
        cp = ord(ch)
        for lo, hi, lang in _SCRIPT_RANGES:
            if lo <= cp <= hi:
                counts[lang] = counts.get(lang, 0) + 1
                break
    if not counts:
        return None
    best = max(counts, key=counts.__getitem__)
    return best if counts[best] >= 3 else None


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
    lang_parts = set(lang_iso.split("+"))

    # Documentos da Igreja
    if coll in COLLECTION_DOCUMENT_SECTIONS:
        return "documentos", None, COLLECTION_TO_DOCTYPE.get(coll, "outro")

    # Tradução / vernáculo → Patrística em Português
    if not is_primary_source or lang_parts & TRANSLATION_LANGS:
        return "patristica", "portuguesa", None

    # Patrística Grega
    if coll == "PG" or lang_parts & {"grc", "el"}:
        return "patristica", "grega", None

    # Patrística Oriental
    if coll == "PO" or lang_parts & ORIENTAL_LANGS:
        return "patristica", "oriental", None

    # Patrística Latina (PL ou padrão)
    return "patristica", "latina", None
