"""
Parser semântico de metadados de livros patrísticos.

Detecta automaticamente a partir do texto do filename + amostra de páginas:
  - Autor canônico e obra
  - Coletâneas (volumes com múltiplos autores)
  - Editora (Paulus, Loyola…)
  - Idioma/variante (pt-BR)
  - Tradição patrística (portuguesa para edições Paulus em PT)
"""
import re
import unicodedata
from dataclasses import dataclass, asdict
from typing import Any


def _norm(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text


@dataclass
class ParsedPatristicBook:
    title: str | None = None
    canonical_title: str | None = None
    display_title: str | None = None

    author: str | None = None
    canonical_author: str | None = None

    is_collectanea: bool = False
    collectanea_label: str | None = None
    included_authors: list[str] | None = None
    included_works: list[str] | None = None

    library_section: str | None = None
    patristic_tradition: str | None = None

    language: str | None = None
    country_variant: str | None = None

    publisher: str | None = None
    editorial_collection: str | None = None
    edition_type: str | None = None

    historical_reference_collection: str | None = None
    source_is_primary_edition: bool = False

    notes: list[str] | None = None


PUBLISHER_PATTERNS = {
    "Paulus": [r"\bpaulus\b"],
    "Loyola": [r"\bloyola\b"],
}

PT_BR_MARKERS = {
    "apresentacao",
    "introducao",
    "traducao",
    "editora",
    "indice",
    "obra",
    "livro",
    "igreja",
    "padres",
    "patristica",
    "contra as heresias",
    "dialogo com trifao",
}

COLLECTANEA_PATTERNS = {
    "Padres Apostólicos": [
        r"\bpadres apostolicos\b",
        r"\bclemente romano\b",
        r"\binacio de antioquia\b",
        r"\bpolicarpo de esmirna\b",
        r"\bo pastor de hermas\b",
        r"\bcarta de barnabe\b",
        r"\bpapias\b",
        r"\bdidaque\b",
    ],
    "Padres Apologistas": [
        r"\bpadres apologistas\b",
        r"\bcarta a diogneto\b",
        r"\baristides de atenas\b",
        r"\btaciano\b",
        r"\batenagoras de atenas\b",
        r"\bteofilo de antioquia\b",
        r"\bhermias\b",
    ],
}

AUTHOR_DB: dict[str, dict[str, Any]] = {
    "Santo Irineu de Lião": {
        "patterns": [r"\birineu de liao\b", r"\bireneu\b", r"\birineu\b"],
        "tradition": "grega",
        "works": {
            "Contra as Heresias": [r"\bcontra as heresias\b"],
        },
    },
    "São Justino Mártir": {
        "patterns": [r"\bjustino de roma\b", r"\bsao justino\b", r"\bjustino martir\b"],
        "tradition": "grega",
        "works": {
            "I e II Apologias; Diálogo com Trifão": [
                r"\bi e ii apologias\b",
                r"\bdialogo com trifao\b",
            ],
        },
    },
    "São Clemente Romano": {
        "patterns": [r"\bclemente romano\b"],
        "tradition": "grega",
        "works": {},
    },
    "Santo Inácio de Antioquia": {
        "patterns": [r"\binacio de antioquia\b"],
        "tradition": "grega",
        "works": {},
    },
    "São Policarpo de Esmirna": {
        "patterns": [r"\bpolicarpo de esmirna\b"],
        "tradition": "grega",
        "works": {},
    },
    "Hermas": {
        "patterns": [r"\bhermas\b", r"\bo pastor de hermas\b"],
        "tradition": "grega",
        "works": {},
    },
    "Autor da Carta de Barnabé": {
        "patterns": [r"\bcarta de barnabe\b"],
        "tradition": "grega",
        "works": {},
    },
    "Pápias de Hierápolis": {
        "patterns": [r"\bpapias\b"],
        "tradition": "grega",
        "works": {},
    },
    "Didaqué": {
        "patterns": [r"\bdidaque\b"],
        "tradition": "grega",
        "works": {},
    },
    "Arístides de Atenas": {
        "patterns": [r"\baristides de atenas\b"],
        "tradition": "grega",
        "works": {},
    },
    "Taciano, o Sírio": {
        "patterns": [r"\btaciano\b", r"\btaciano o sirio\b"],
        "tradition": "grega",
        "works": {},
    },
    "Atenágoras de Atenas": {
        "patterns": [r"\batenagoras de atenas\b"],
        "tradition": "grega",
        "works": {},
    },
    "Teófilo de Antioquia": {
        "patterns": [r"\bteofilo de antioquia\b"],
        "tradition": "grega",
        "works": {},
    },
    "Hérmias, o Filósofo": {
        "patterns": [r"\bhermias\b", r"\bhermias o filosofo\b"],
        "tradition": "grega",
        "works": {},
    },
}


def detect_language_pt_br(text: str) -> tuple[str | None, str | None]:
    t = _norm(text)
    hits = sum(1 for marker in PT_BR_MARKERS if marker in t)
    if hits >= 3:
        return "pt", "pt-BR"
    return None, None


def detect_publisher(text: str) -> str | None:
    t = _norm(text)
    for publisher, patterns in PUBLISHER_PATTERNS.items():
        for p in patterns:
            if re.search(p, t):
                return publisher
    return None


def detect_editorial_collection(text: str) -> str | None:
    t = _norm(text)
    if "patristica" in t:
        return "Patrística"
    return None


def detect_collectanea(text: str) -> tuple[bool, str | None, list[str], list[str]]:
    t = _norm(text)

    for label, patterns in COLLECTANEA_PATTERNS.items():
        matched = sum(1 for p in patterns if re.search(p, t))

        if matched >= 3:
            included = []
            for author_name, data in AUTHOR_DB.items():
                for p in data["patterns"]:
                    if re.search(p, t):
                        included.append(author_name)
                        break

            works: list[str] = []
            if label == "Padres Apostólicos":
                works = [
                    "Primeira Carta de Clemente aos Coríntios",
                    "Cartas de Inácio de Antioquia",
                    "Cartas de Policarpo",
                    "O Pastor de Hermas",
                    "Carta de Barnabé",
                    "Fragmentos de Pápias",
                    "Didaqué",
                ]
            elif label == "Padres Apologistas":
                works = [
                    "Carta a Diogneto",
                    "Apologia de Arístides",
                    "Discurso contra os Gregos",
                    "Petição em Favor dos Cristãos",
                    "A Autólico",
                    "Escárnio dos Filósofos Pagãos",
                ]

            return True, label, sorted(set(included)), works

    return False, None, [], []


def detect_single_author_and_work(
    text: str,
) -> tuple[str | None, str | None, str | None]:
    t = _norm(text)

    scored_authors: list[tuple[str, int]] = []
    for author_name, data in AUTHOR_DB.items():
        score = sum(2 for p in data["patterns"] if re.search(p, t))
        if score > 0:
            scored_authors.append((author_name, score))

    scored_authors.sort(key=lambda x: x[1], reverse=True)

    if not scored_authors:
        return None, None, None

    # Empate entre dois autores → ambíguo, não forçar
    if len(scored_authors) > 1 and scored_authors[0][1] == scored_authors[1][1]:
        return None, None, None

    best_author = scored_authors[0][0]
    tradition = AUTHOR_DB[best_author]["tradition"]

    canonical_title = None
    for work_name, patterns in AUTHOR_DB[best_author]["works"].items():
        for p in patterns:
            if re.search(p, t):
                canonical_title = work_name
                break
        if canonical_title:
            break

    return best_author, canonical_title, tradition


def parse_patristic_book(metadata_text: str) -> ParsedPatristicBook:
    """
    Ponto de entrada principal. Recebe texto livre (filename + amostra de páginas)
    e retorna metadados estruturados.
    """
    notes: list[str] = []
    lang, variant = detect_language_pt_br(metadata_text)
    publisher = detect_publisher(metadata_text)
    editorial_collection = detect_editorial_collection(metadata_text)

    is_collectanea, collectanea_label, included_authors, included_works = detect_collectanea(
        metadata_text
    )

    author: str | None = None
    canonical_author: str | None = None
    canonical_title: str | None = None
    patristic_tradition: str | None = None

    if is_collectanea:
        author = collectanea_label
        canonical_author = collectanea_label
        canonical_title = collectanea_label
        patristic_tradition = (
            "grega"
            if collectanea_label in {"Padres Apostólicos", "Padres Apologistas"}
            else None
        )
        notes.append("Volume tratado como coletânea; não forçar autor único.")
    else:
        best_author, best_title, best_tradition = detect_single_author_and_work(metadata_text)
        author = best_author
        canonical_author = best_author
        canonical_title = best_title
        patristic_tradition = best_tradition

    # Edição Paulus em PT → tradição = "portuguesa" (não PG/PL do arquivo)
    if publisher == "Paulus" and lang == "pt":
        patristic_tradition = "portuguesa"
        notes.append("Edição em português da Paulus detectada.")
        notes.append("Classificar em Patrística em Português, não como PG/PL do próprio arquivo.")

    display_title = canonical_title or collectanea_label or author

    return ParsedPatristicBook(
        title=display_title,
        canonical_title=canonical_title,
        display_title=display_title,
        author=author,
        canonical_author=canonical_author,
        is_collectanea=is_collectanea,
        collectanea_label=collectanea_label,
        included_authors=included_authors or None,
        included_works=included_works or None,
        library_section="patristica",
        patristic_tradition=patristic_tradition,
        language=lang,
        country_variant=variant,
        publisher=publisher,
        editorial_collection=editorial_collection,
        edition_type="traducao_portuguesa" if lang == "pt" else None,
        historical_reference_collection=None,
        source_is_primary_edition=False,
        notes=notes or None,
    )


if __name__ == "__main__":
    samples = [
        """
        PATRÍSTICA
        CONTRA AS HERESIAS
        Irineu de Lião
        Paulus
        Apresentação
        Introdução
        """,
        """
        PATRÍSTICA
        PADRES APOSTÓLICOS
        Clemente Romano
        Inácio de Antioquia
        Policarpo de Esmirna
        O pastor de Hermas
        Carta de Barnabé
        Pápias
        Didaqué
        Paulus
        Índice
        """,
        """
        PATRÍSTICA
        PADRES APOLOGISTAS
        Carta a Diogneto
        Aristides de Atenas
        Taciano, o Sírio
        Atenágoras de Atenas
        Teófilo de Antioquia
        Hérmias, o Filósofo
        Paulus
        """,
        """
        PATRÍSTICA
        JUSTINO DE ROMA
        I e II Apologias
        Diálogo com Trifão
        Paulus
        Apresentação
        """,
    ]

    for i, sample in enumerate(samples, start=1):
        result = parse_patristic_book(sample)
        print(f"\n--- SAMPLE {i} ---")
        for k, v in asdict(result).items():
            if v is not None:
                print(f"  {k}: {v}")
