"""Build PDFs for all 21 Ecumenical Councils.

Scrapes text from Vatican.va, New Advent, Apologistas Católicos and other
sources, then generates professionally styled PDFs matching the Vatican.va
aesthetic used throughout the Vera.Fidei library.

Usage:
    python build_council_pdfs.py
    python build_council_pdfs.py --council niceia-i --lang pt
    python build_council_pdfs.py --dry-run
    python build_council_pdfs.py --ai-translate --delay 1.5
"""

from __future__ import annotations

import argparse
import html
import os
import re
import shutil
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf-8-sig"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
import subprocess
import textwrap
import time
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable

import requests


BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = BACKEND_DIR / "pdfs" / "concilios"
DEFAULT_HTML_DIR = BACKEND_DIR / ".tmp_council_html"

VATICAN2_BASE = "https://www.vatican.va/archive/hist_councils/ii_vatican_council/documents/"
VATICAN1_BASE = "https://www.vatican.va/archive/hist_councils/i-vatican-council/documents/"

# Vatican.va language code suffix per language tag
V2_LANG: dict[str, str] = {"pt": "po", "en": "en", "it": "it", "la": "lt", "de": "ge", "es": "sp"}

# Vatican I only has Italian and Latin officially on Vatican.va
V1_LANG: dict[str, str] = {"it": "it", "la": "lt"}

SOURCE_LABELS: dict[str, str] = {
    "vatican.va": "Vatican.va",
    "newadvent": "New Advent / NPNF",
    "apologistas": "Apologistas Católicos",
    "elpenor": "Elpenor.org",
    "dca": "Documenta Catholica Omnia",
    "ai": "Tradução Assistida por IA (Vera.Fidei)",
}

# ─── Council document definitions ─────────────────────────────────────────────

@dataclass
class LangSource:
    lang: str        # "pt", "en", "la", "gr", "it", "de", "es"
    url: str         # fetch URL
    site: str        # key into SOURCE_LABELS
    encoding: str = "utf-8"


@dataclass
class CouncilDocument:
    title: str
    doc_type: str        # e.g. "Cânones e Documentos", "Constituição Dogmática"
    sources: list[LangSource] = field(default_factory=list)
    ai_langs: list[str] = field(default_factory=list)  # generate via AI if source missing


@dataclass
class Council:
    key: str             # slug, e.g. "niceia-i"
    number: int
    year: int
    year_end: int | None
    century: str         # "IV (325-381)"
    display_name: str    # "Concílio de Nicéia I"
    folder_name: str     # "01 - 325 - Niceia I"
    documents: list[CouncilDocument] = field(default_factory=list)


def _v2_sources(slug: str, langs: Iterable[str] = V2_LANG) -> list[LangSource]:
    return [
        LangSource(
            lang=lang,
            url=f"{VATICAN2_BASE}{slug}_{code}.html",
            site="vatican.va",
        )
        for lang, code in V2_LANG.items()
        if lang in langs
    ]


def _v1_sources(slug: str) -> list[LangSource]:
    """Vatican I official sources (IT + LA only)."""
    return [
        LangSource(lang=lang, url=f"{VATICAN1_BASE}{slug}_{code}.html", site="vatican.va")
        for lang, code in V1_LANG.items()
    ]


def _na(code: str) -> str:
    """New Advent NPNF URL."""
    return f"https://www.newadvent.org/fathers/{code}.htm"


def _ap(af_id: str) -> str:
    """Apologistas.com.br URL."""
    return f"https://apologistascatolicos.com.br/conciliosecumenicos/index.php?af={af_id}"


COUNCILS: list[Council] = [
    # ── Século IV ────────────────────────────────────────────────────────────
    Council(
        key="niceia-i", number=1, year=325, year_end=None,
        century="IV (325-381)",
        display_name="Concílio de Nicéia I",
        folder_name="01 - 325 - Niceia I",
        documents=[
            CouncilDocument(
                title="Cânones e Documentos",
                doc_type="Concílio Ecumênico — Cânones",
                sources=[
                    LangSource("pt", _ap("ConcilioDeNiceiaI"), "apologistas"),
                    LangSource("en", _na("3801"), "newadvent"),
                    LangSource("gr", "https://www.elpenor.org/ecumenical-councils/first.asp", "elpenor"),
                ],
                ai_langs=["it", "de", "es", "la"],
            ),
        ],
    ),
    Council(
        key="constantinopla-i", number=2, year=381, year_end=None,
        century="IV (325-381)",
        display_name="Concílio de Constantinopla I",
        folder_name="02 - 381 - Constantinopla I",
        documents=[
            CouncilDocument(
                title="Cânones e Documentos",
                doc_type="Concílio Ecumênico — Cânones",
                sources=[
                    LangSource("pt", _ap("ConcilioDeConstantinoplaI"), "apologistas"),
                    LangSource("en", _na("3802"), "newadvent"),
                    LangSource("gr", "https://www.elpenor.org/ecumenical-councils/second.asp", "elpenor"),
                ],
                ai_langs=["it", "de", "es", "la"],
            ),
        ],
    ),
    # ── Século V ─────────────────────────────────────────────────────────────
    Council(
        key="efeso", number=3, year=431, year_end=None,
        century="V (431-451)",
        display_name="Concílio de Éfeso",
        folder_name="03 - 431 - Efeso",
        documents=[
            CouncilDocument(
                title="Cânones e Documentos",
                doc_type="Concílio Ecumênico — Cânones",
                sources=[
                    LangSource("pt", _ap("ConcilioDeEfeso"), "apologistas"),
                    LangSource("en", _na("3803"), "newadvent"),
                ],
                ai_langs=["it", "de", "es", "la", "gr"],
            ),
        ],
    ),
    Council(
        key="calcedonia", number=4, year=451, year_end=None,
        century="V (431-451)",
        display_name="Concílio de Calcedônia",
        folder_name="04 - 451 - Calcedonia",
        documents=[
            CouncilDocument(
                title="Cânones e Atos",
                doc_type="Concílio Ecumênico — Cânones",
                sources=[
                    LangSource("pt", _ap("ConcilioDeCalecedon"), "apologistas"),
                    LangSource("en", _na("3811"), "newadvent"),
                ],
                ai_langs=["it", "de", "es", "la", "gr"],
            ),
        ],
    ),
    # ── Século VI ────────────────────────────────────────────────────────────
    Council(
        key="constantinopla-ii", number=5, year=553, year_end=None,
        century="VI (553)",
        display_name="Concílio de Constantinopla II",
        folder_name="05 - 553 - Constantinopla II",
        documents=[
            CouncilDocument(
                title="Cânones e Documentos",
                doc_type="Concílio Ecumênico — Cânones",
                sources=[
                    LangSource("pt", _ap("ConcilioDeConstantinoplaII"), "apologistas"),
                    LangSource("en", _na("3813"), "newadvent"),
                ],
                ai_langs=["it", "de", "es", "la", "gr"],
            ),
        ],
    ),
    # ── Século VII ───────────────────────────────────────────────────────────
    Council(
        key="constantinopla-iii", number=6, year=680, year_end=681,
        century="VII (680-692)",
        display_name="Concílio de Constantinopla III",
        folder_name="06 - 680 - Constantinopla III",
        documents=[
            CouncilDocument(
                title="Cânones e Documentos",
                doc_type="Concílio Ecumênico — Cânones",
                sources=[
                    LangSource("pt", _ap("ConcilioDeConstantinoplaIII"), "apologistas"),
                    LangSource("en", _na("3814"), "newadvent"),
                ],
                ai_langs=["it", "de", "es", "la", "gr"],
            ),
        ],
    ),
    # ── Século VIII ──────────────────────────────────────────────────────────
    Council(
        key="niceia-ii", number=7, year=787, year_end=None,
        century="VIII (787)",
        display_name="Concílio de Nicéia II",
        folder_name="07 - 787 - Niceia II",
        documents=[
            CouncilDocument(
                title="Cânones e Documentos",
                doc_type="Concílio Ecumênico — Cânones",
                sources=[
                    LangSource("pt", _ap("ConcilioDeNiceiaII"), "apologistas"),
                    LangSource("en", _na("3820"), "newadvent"),
                    LangSource("gr", "https://www.elpenor.org/ecumenical-councils/seventh.asp", "elpenor"),
                ],
                ai_langs=["it", "de", "es", "la"],
            ),
        ],
    ),
    # ── Século IX ────────────────────────────────────────────────────────────
    Council(
        key="constantinopla-iv", number=8, year=869, year_end=870,
        century="IX (869-870)",
        display_name="Concílio de Constantinopla IV",
        folder_name="08 - 869 - Constantinopla IV",
        documents=[
            CouncilDocument(
                title="Cânones e Documentos",
                doc_type="Concílio Ecumênico — Cânones",
                sources=[
                    LangSource("pt", _ap("ConcilioDeConstantinoplaIV"), "apologistas"),
                    LangSource("en", "https://www.papalencyclicals.net/councils/ecum08.htm", "newadvent"),
                ],
                ai_langs=["it", "de", "es", "la", "gr"],
            ),
        ],
    ),
    # ── Século XII ───────────────────────────────────────────────────────────
    Council(
        key="latrao-i", number=9, year=1123, year_end=None,
        century="XII (1123-1179)",
        display_name="Concílio do Latrão I",
        folder_name="09 - 1123 - Latrao I",
        documents=[
            CouncilDocument(
                title="Cânones",
                doc_type="Concílio Ecumênico — Cânones",
                sources=[
                    LangSource("pt", _ap("ConcilioDeLatraoI"), "apologistas"),
                    LangSource("en", "https://www.ewtn.com/catholicism/library/first-lateran-council-1123-1481", "newadvent"),
                ],
                ai_langs=["it", "de", "es", "la", "gr"],
            ),
        ],
    ),
    Council(
        key="latrao-ii", number=10, year=1139, year_end=None,
        century="XII (1123-1179)",
        display_name="Concílio do Latrão II",
        folder_name="10 - 1139 - Latrao II",
        documents=[
            CouncilDocument(
                title="Cânones",
                doc_type="Concílio Ecumênico — Cânones",
                sources=[
                    LangSource("pt", _ap("ConcilioDeLatraoII"), "apologistas"),
                    LangSource("en", "https://www.ewtn.com/catholicism/library/second-lateran-council-1139-1484", "newadvent"),
                ],
                ai_langs=["it", "de", "es", "la", "gr"],
            ),
        ],
    ),
    Council(
        key="latrao-iii", number=11, year=1179, year_end=None,
        century="XII (1123-1179)",
        display_name="Concílio do Latrão III",
        folder_name="11 - 1179 - Latrao III",
        documents=[
            CouncilDocument(
                title="Cânones",
                doc_type="Concílio Ecumênico — Cânones",
                sources=[
                    LangSource("pt", _ap("ConcilioDeLatraoIII"), "apologistas"),
                    LangSource("en", "https://www.ewtn.com/catholicism/library/third-lateran-council-1179-1487", "newadvent"),
                ],
                ai_langs=["it", "de", "es", "la", "gr"],
            ),
        ],
    ),
    # ── Século XIII ──────────────────────────────────────────────────────────
    Council(
        key="latrao-iv", number=12, year=1215, year_end=None,
        century="XIII (1215-1274)",
        display_name="Concílio do Latrão IV",
        folder_name="12 - 1215 - Latrao IV",
        documents=[
            CouncilDocument(
                title="Cânones e Constituições",
                doc_type="Concílio Ecumênico — Constituições",
                sources=[
                    LangSource("pt", _ap("ConcilioDeLatraoIV"), "apologistas"),
                    LangSource("en", _na("3806"), "newadvent"),
                ],
                ai_langs=["it", "de", "es", "la", "gr"],
            ),
        ],
    ),
    Council(
        key="liao-i", number=13, year=1245, year_end=None,
        century="XIII (1215-1274)",
        display_name="Concílio de Lião I",
        folder_name="13 - 1245 - Liao I",
        documents=[
            CouncilDocument(
                title="Cânones e Documentos",
                doc_type="Concílio Ecumênico — Cânones",
                sources=[
                    LangSource("pt", _ap("ConcilioDeLiaoI"), "apologistas"),
                    LangSource("en", "https://www.ewtn.com/catholicism/library/first-council-of-lyons-1245-1489", "newadvent"),
                ],
                ai_langs=["it", "de", "es", "la", "gr"],
            ),
        ],
    ),
    Council(
        key="liao-ii", number=14, year=1274, year_end=None,
        century="XIII (1215-1274)",
        display_name="Concílio de Lião II",
        folder_name="14 - 1274 - Liao II",
        documents=[
            CouncilDocument(
                title="Cânones e Documentos",
                doc_type="Concílio Ecumênico — Cânones",
                sources=[
                    LangSource("pt", _ap("ConcilioDeLiaoII"), "apologistas"),
                    LangSource("en", "https://www.ewtn.com/catholicism/library/second-council-of-lyons-1274-1491", "newadvent"),
                ],
                ai_langs=["it", "de", "es", "la", "gr"],
            ),
        ],
    ),
    # ── Século XIV ───────────────────────────────────────────────────────────
    Council(
        key="viena", number=15, year=1311, year_end=1312,
        century="XIV (1311-1312)",
        display_name="Concílio de Viena",
        folder_name="15 - 1311 - Viena",
        documents=[
            CouncilDocument(
                title="Decretos",
                doc_type="Concílio Ecumênico — Decretos",
                sources=[
                    LangSource("pt", _ap("ConcilioDeViena"), "apologistas"),
                    LangSource("en", "https://www.ewtn.com/catholicism/library/council-of-vienne-1311-1493", "newadvent"),
                ],
                ai_langs=["it", "de", "es", "la", "gr"],
            ),
        ],
    ),
    # ── Século XV ────────────────────────────────────────────────────────────
    Council(
        key="constanca", number=16, year=1414, year_end=1418,
        century="XV (1414-1449)",
        display_name="Concílio de Constança",
        folder_name="16 - 1414 - Constanca",
        documents=[
            CouncilDocument(
                title="Decretos e Documentos",
                doc_type="Concílio Ecumênico — Decretos",
                sources=[
                    LangSource("pt", _ap("ConcilioDeConstanca"), "apologistas"),
                    LangSource("en", "https://www.ewtn.com/catholicism/library/council-of-constance-1414-1497", "newadvent"),
                ],
                ai_langs=["it", "de", "es", "la", "gr"],
            ),
        ],
    ),
    Council(
        key="florenca", number=17, year=1438, year_end=1445,
        century="XV (1414-1449)",
        display_name="Concílio de Basileia-Ferrara-Florença",
        folder_name="17 - 1438 - Florenca",
        documents=[
            CouncilDocument(
                title="Decretos de União",
                doc_type="Concílio Ecumênico — Decretos",
                sources=[
                    LangSource("pt", _ap("ConcilioDeBasileiaFerraraFlorenca"), "apologistas"),
                    LangSource("en", "https://www.ewtn.com/catholicism/library/council-of-florence-1438-1500", "newadvent"),
                ],
                ai_langs=["it", "de", "es", "la", "gr"],
            ),
        ],
    ),
    # ── Século XVI ───────────────────────────────────────────────────────────
    Council(
        key="latrao-v", number=18, year=1512, year_end=1517,
        century="XVI (1512-1563)",
        display_name="Concílio do Latrão V",
        folder_name="18 - 1512 - Latrao V",
        documents=[
            CouncilDocument(
                title="Bulas e Decretos",
                doc_type="Concílio Ecumênico — Decretos",
                sources=[
                    LangSource("pt", _ap("ConcilioDeLatraoV"), "apologistas"),
                    LangSource("en", "https://www.ewtn.com/catholicism/library/fifth-lateran-council-1512-1503", "newadvent"),
                ],
                ai_langs=["it", "de", "es", "la", "gr"],
            ),
        ],
    ),
    Council(
        key="trento", number=19, year=1545, year_end=1563,
        century="XVI (1512-1563)",
        display_name="Concílio de Trento",
        folder_name="19 - 1545 - Trento",
        documents=[
            CouncilDocument(
                title="Cânones e Decretos Dogmáticos",
                doc_type="Concílio Ecumênico — Cânones e Decretos",
                sources=[
                    LangSource("pt", _ap("ConcilioDeTrento"), "apologistas"),
                    LangSource("en", "https://www.ewtn.com/catholicism/library/canons-and-decrees-of-the-council-of-trent-1548", "newadvent"),
                ],
                ai_langs=["it", "de", "es", "la", "gr"],
            ),
        ],
    ),
    # ── Século XIX ───────────────────────────────────────────────────────────
    Council(
        key="vaticano-i", number=20, year=1869, year_end=1870,
        century="XIX (1869-1870)",
        display_name="Concílio Vaticano I",
        folder_name="20 - 1869 - Vaticano I",
        documents=[
            CouncilDocument(
                title="Dei Filius",
                doc_type="Constituição Dogmática",
                sources=[
                    LangSource("it", f"{VATICAN1_BASE}vat-i_const_18700424_dei-filius_it.html", "vatican.va"),
                    LangSource("la", f"{VATICAN1_BASE}vat-i_const_18700424_dei-filius_la.html", "vatican.va"),
                    LangSource("en", "https://www.ewtn.com/catholicism/library/first-dogmatic-constitution-on-the-church-of-christ-1457", "newadvent"),
                    LangSource("pt", _ap("ConcilioVaticanoI"), "apologistas"),
                ],
                ai_langs=["de", "es", "gr"],
            ),
            CouncilDocument(
                title="Pastor Aeternus",
                doc_type="Constituição Dogmática",
                sources=[
                    LangSource("it", f"{VATICAN1_BASE}vat-i_const_18700718_pastor-aeternus_it.html", "vatican.va"),
                    LangSource("la", f"{VATICAN1_BASE}vat-i_const_18700718_pastor-aeternus_la.html", "vatican.va"),
                    LangSource("en", "https://www.ewtn.com/catholicism/library/first-dogmatic-constitution-on-the-church-of-christ-1457", "newadvent"),
                ],
                ai_langs=["pt", "de", "es", "gr"],
            ),
        ],
    ),
    # ── Século XX ────────────────────────────────────────────────────────────
    Council(
        key="vaticano-ii", number=21, year=1962, year_end=1965,
        century="XX (1962-1965)",
        display_name="Concílio Vaticano II",
        folder_name="21 - 1962 - Vaticano II",
        documents=[
            CouncilDocument(
                title="Lumen Gentium",
                doc_type="Constituição Dogmática",
                sources=_v2_sources("vat-ii_const_19641121_lumen-gentium"),
            ),
            CouncilDocument(
                title="Dei Verbum",
                doc_type="Constituição Dogmática",
                sources=_v2_sources("vat-ii_const_19651118_dei-verbum"),
            ),
            CouncilDocument(
                title="Sacrosanctum Concilium",
                doc_type="Constituição",
                sources=_v2_sources("vat-ii_const_19631204_sacrosanctum-concilium"),
            ),
            CouncilDocument(
                title="Gaudium et Spes",
                doc_type="Constituição Pastoral",
                sources=_v2_sources("vat-ii_const_19651207_gaudium-et-spes"),
            ),
            CouncilDocument(
                title="Ad Gentes",
                doc_type="Decreto",
                sources=_v2_sources("vat-ii_decree_19651207_ad-gentes"),
            ),
            CouncilDocument(
                title="Presbyterorum Ordinis",
                doc_type="Decreto",
                sources=_v2_sources("vat-ii_decree_19651207_presbyterorum-ordinis"),
            ),
            CouncilDocument(
                title="Apostolicam Actuositatem",
                doc_type="Decreto",
                sources=_v2_sources("vat-ii_decree_19651118_apostolicam-actuositatem"),
            ),
            CouncilDocument(
                title="Optatam Totius",
                doc_type="Decreto",
                sources=_v2_sources("vat-ii_decree_19651028_optatam-totius"),
            ),
            CouncilDocument(
                title="Perfectae Caritatis",
                doc_type="Decreto",
                sources=_v2_sources("vat-ii_decree_19651028_perfectae-caritatis"),
            ),
            CouncilDocument(
                title="Christus Dominus",
                doc_type="Decreto",
                sources=_v2_sources("vat-ii_decree_19651028_christus-dominus"),
            ),
            CouncilDocument(
                title="Unitatis Redintegratio",
                doc_type="Decreto",
                sources=_v2_sources("vat-ii_decree_19641121_unitatis-redintegratio"),
            ),
            CouncilDocument(
                title="Orientalium Ecclesiarum",
                doc_type="Decreto",
                sources=_v2_sources("vat-ii_decree_19641121_orientalium-ecclesiarum"),
            ),
            CouncilDocument(
                title="Inter Mirifica",
                doc_type="Decreto",
                sources=_v2_sources("vat-ii_decree_19631204_inter-mirifica"),
            ),
            CouncilDocument(
                title="Gravissimum Educationis",
                doc_type="Declaração",
                sources=_v2_sources("vat-ii_decl_19651028_gravissimum-educationis"),
            ),
            CouncilDocument(
                title="Nostra Aetate",
                doc_type="Declaração",
                sources=_v2_sources("vat-ii_decl_19651028_nostra-aetate"),
            ),
            CouncilDocument(
                title="Dignitatis Humanae",
                doc_type="Declaração",
                sources=_v2_sources("vat-ii_decl_19651207_dignitatis-humanae"),
            ),
        ],
    ),
]

COUNCIL_BY_KEY: dict[str, Council] = {c.key: c for c in COUNCILS}

# ─── HTML parsing ─────────────────────────────────────────────────────────────

class TextHTMLParser(HTMLParser):
    block_tags = {
        "address", "article", "aside", "blockquote", "br", "center",
        "dd", "div", "dl", "dt", "figcaption", "form",
        "h1", "h2", "h3", "h4", "h5", "h6", "hr", "li",
        "main", "ol", "p", "pre", "section", "table", "td",
        "th", "title", "tr", "ul",
    }
    skip_tags = {"script", "style", "noscript"}
    # Skip entire structural chrome elements (nav, header, footer)
    chrome_tags = {"nav", "header", "footer"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0
        self._chrome_depth = 0
        self._in_body = False
        self._seen_body = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "body":
            self._in_body = True
            self._seen_body = True
        if tag in self.skip_tags:
            self._skip_depth += 1
        if tag in self.chrome_tags:
            self._chrome_depth += 1
        # Also skip <div id="nav">, <div class="breadcrumb"> etc.
        if tag == "div":
            attrs_dict = dict(attrs)
            val = (attrs_dict.get("id") or "") + " " + (attrs_dict.get("class") or "")
            if any(k in val.lower() for k in ("nav", "menu", "breadcrumb", "sidebar", "header", "footer")):
                self._chrome_depth += 1
        if self._accept_text() and tag in self.block_tags:
            self._newline()
            if tag == "li":
                self.parts.append("- ")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.skip_tags and self._skip_depth:
            self._skip_depth -= 1
        if tag in self.chrome_tags and self._chrome_depth:
            self._chrome_depth -= 1
        if tag == "div" and self._chrome_depth:
            self._chrome_depth -= 1
        if self._accept_text() and tag in self.block_tags:
            self._newline()
        if tag == "body":
            self._in_body = False

    def handle_data(self, data: str) -> None:
        if not self._accept_text():
            return
        data = data.replace("\xa0", " ")
        data = re.sub(r"\s+", " ", data)
        if data.strip():
            self.parts.append(data)

    def _accept_text(self) -> bool:
        return self._skip_depth == 0 and self._chrome_depth == 0 and (self._in_body or not self._seen_body)

    def _newline(self) -> None:
        if self.parts and not self.parts[-1].endswith("\n"):
            self.parts.append("\n")
        if self.parts and self.parts[-1] != "\n\n":
            self.parts.append("\n")

    def paragraphs(self) -> list[str]:
        raw = "".join(self.parts).replace("﻿", "")
        lines = [_clean(line) for line in raw.splitlines()]
        paragraphs: list[str] = []
        current: list[str] = []
        for line in lines:
            if not line:
                if current:
                    paragraphs.append(_clean(" ".join(current)))
                    current = []
                continue
            current.append(line)
        if current:
            paragraphs.append(_clean(" ".join(current)))
        return [p for p in paragraphs if p and not _should_drop(p)]


def _clean(text: str) -> str:
    text = text.replace("﻿", "").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _should_drop(text: str) -> bool:
    lowered = text.lower()
    stripped = text.strip()

    # Standard noise
    noise = {"advertisement", "copyright", "all rights reserved", "javascript"}
    if any(n in lowered for n in noise):
        return True
    if lowered.startswith("javascript:"):
        return True

    # Pipe-separated breadcrumb navigation ("Home | Patrística | Concílios")
    if "|" in stripped and len(stripped) < 150:
        parts = [p.strip() for p in stripped.split("|")]
        if all(len(p) < 50 for p in parts):
            return True

    # CamelCase slugs without spaces (e.g. "ConcilioDeLatraoV")
    if re.match(r'^[A-Z][a-z]+(?:[A-Z][a-z0-9]+){2,}$', stripped):
        return True

    # Stray HTML tag fragments leaked as text: "/td>", "div>", etc.
    if re.match(r'^/?[a-zA-Z]{1,10}>$', stripped):
        return True

    # Translation request message from apologistas site
    if 'ajude-nos traduzindo' in lowered:
        return True

    # Single nav keyword items
    nav_words = {'home', 'patristica', 'patrística', 'deuterocanonicos', 'deuterocanônicos',
                 'concilios', 'concílios', 'ecumenicos', 'ecuménicos'}
    if stripped.lower().rstrip('|').strip() in nav_words:
        return True

    return False


def _is_english_content(paragraphs: list[str]) -> bool:
    """Heuristic: returns True if paragraphs appear to be in English, not Portuguese."""
    text = " " + " ".join(paragraphs[:10]).lower() + " "
    pt_markers = [" de ", " do ", " da ", " que ", " em ", " para ", " com ", " não ", " são ", " uma ", " nos "]
    en_markers = [" the ", " that ", " which ", " thereof ", " shall ", " upon ", " without ", " hereby ", " canon "]
    pt_count = sum(text.count(m) for m in pt_markers)
    en_count = sum(text.count(m) for m in en_markers)
    return en_count >= 3 and en_count > pt_count


def parse_body_paragraphs(html_text: str) -> list[str]:
    parser = TextHTMLParser()
    parser.feed(html_text)
    return parser.paragraphs()


# ─── HTTP fetching ────────────────────────────────────────────────────────────

def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Vera.Fidei Biblioteca/1.0 (+local research archive; contact: local)",
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8,la;q=0.7",
    })
    return session


def fetch_text(url: str, session: requests.Session, encoding: str = "utf-8") -> str:
    resp = session.get(url, timeout=45)
    resp.raise_for_status()
    try:
        return resp.content.decode("utf-8-sig")
    except UnicodeDecodeError:
        resp.encoding = resp.apparent_encoding or encoding
        return resp.text


# ─── PDF helpers (adapted from build_encyclical_pdfs.py) ─────────────────────

def sanitize_path_part(text: str, max_len: int = 120) -> str:
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r'[<>:"/\\|?*]+', " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    if len(text) > max_len:
        text = text[:max_len].rstrip(" .")
    return text or "sem-titulo"


def wrap_text(text: str, width: int) -> list[str]:
    text = _clean(text)
    if not text:
        return []
    return textwrap.wrap(text, width=width, break_long_words=False, replace_whitespace=True) or [text]


def paragraph_kind(text: str) -> str:
    stripped = text.strip()
    ascii_up = _to_ascii_upper(stripped)
    if len(stripped) <= 90 and stripped.upper() == stripped and re.search(r"[A-Z]", ascii_up):
        return "heading"
    if len(stripped) <= 70 and re.match(
        r"^(CAPITULO|INTRODUCAO|CONCLUSAO|CANONE|CANON|SESSION|I\.|II\.|III\.|IV\.|V\.)", ascii_up
    ):
        return "subheading"
    return "body"


def _to_ascii_upper(text: str) -> str:
    replacements = {
        "á": "a", "à": "a", "â": "a", "ã": "a", "é": "e", "ê": "e",
        "í": "i", "ó": "o", "ô": "o", "õ": "o", "ú": "u", "ç": "c",
        "Á": "A", "À": "A", "Â": "A", "Ã": "A", "É": "E", "Ê": "E",
        "Í": "I", "Ó": "O", "Ô": "O", "Õ": "O", "Ú": "U", "Ç": "C",
    }
    return "".join(replacements.get(c, c) for c in text).upper()


def pdf_escape(text: str) -> bytes:
    text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return text.encode("cp1252", errors="replace")


class SimplePDF:
    width = 595.28
    height = 841.89
    margin_left = 62
    margin_right = 62
    top = 760
    bottom = 72
    body_size = 11.5
    line_height = 15.5

    def __init__(self, title: str, council_name: str, doc_type: str, source_label: str) -> None:
        self.title = title
        self.council_name = council_name
        self.doc_type = doc_type
        self.source_label = source_label
        self.pages: list[list[tuple[str, float, float, float, str]]] = []
        self.current: list[tuple[str, float, float, float, str]] = []
        self.y = self.top
        self.page_number = 0
        self._new_page()

    def add_title_page(self) -> None:
        self._draw_text("Vatican.va", self.margin_left, 690, 12, "italic")
        self._draw_text(self.council_name, self.margin_left, 650, 14, "bold")
        for i, line in enumerate(wrap_text(self.title, 50)):
            self._draw_text(line, self.margin_left, 610 - i * 24, 20, "title")
        self._draw_text(self.doc_type, self.margin_left, 545, 12, "italic")
        self.y = 490

    def add_paragraphs(self, paragraphs: Iterable[str]) -> None:
        for paragraph in paragraphs:
            kind = paragraph_kind(paragraph)
            if kind == "heading":
                self._space(10)
                self._add_wrapped(paragraph, 13.5, "bold", width=58, line_height=18)
                self._space(4)
            elif kind == "subheading":
                self._space(6)
                self._add_wrapped(paragraph, 12.5, "bold", width=66, line_height=17)
                self._space(2)
            else:
                self._add_wrapped(paragraph, self.body_size, "body", width=88, line_height=self.line_height)
                self._space(6)

    def save(self, path: Path) -> None:
        if self.current:
            self.pages.append(self.current)
            self.current = []

        objects: list[bytes] = []

        def add_obj(data: bytes) -> int:
            objects.append(data)
            return len(objects)

        font_body = add_obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Roman /Encoding /WinAnsiEncoding >>")
        font_bold = add_obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Bold /Encoding /WinAnsiEncoding >>")
        font_italic = add_obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Italic /Encoding /WinAnsiEncoding >>")
        font_title = add_obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")

        page_ids: list[int] = []
        content_ids: list[int] = []
        for page_idx, page_lines in enumerate(self.pages, start=1):
            content = self._page_content(page_lines, page_idx, len(self.pages))
            stream = b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream"
            content_ids.append(add_obj(stream))
            page_ids.append(add_obj(b""))

        pages_id = add_obj(b"")
        catalog_id = add_obj(f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode())

        for pid, cid in zip(page_ids, content_ids):
            page = (
                f"<< /Type /Page /Parent {pages_id} 0 R "
                f"/MediaBox [0 0 {self.width:.2f} {self.height:.2f}] "
                f"/Resources << /Font << /F1 {font_body} 0 R /F2 {font_bold} 0 R "
                f"/F3 {font_italic} 0 R /F4 {font_title} 0 R >> >> "
                f"/Contents {cid} 0 R >>"
            )
            objects[pid - 1] = page.encode()

        kids = " ".join(f"{pid} 0 R" for pid in page_ids)
        objects[pages_id - 1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode()

        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as fh:
            fh.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
            offsets = [0]
            for obj_id, data in enumerate(objects, start=1):
                offsets.append(fh.tell())
                fh.write(f"{obj_id} 0 obj\n".encode())
                fh.write(data)
                fh.write(b"\nendobj\n")
            xref = fh.tell()
            fh.write(f"xref\n0 {len(objects) + 1}\n".encode())
            fh.write(b"0000000000 65535 f \n")
            for offset in offsets[1:]:
                fh.write(f"{offset:010d} 00000 n \n".encode())
            fh.write(
                f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
                f"startxref\n{xref}\n%%EOF\n".encode()
            )

    def _new_page(self) -> None:
        if self.current:
            self.pages.append(self.current)
        self.current = []
        self.page_number += 1
        self.y = self.top

    def _draw_text(self, text: str, x: float, y: float, size: float, style: str) -> None:
        self.current.append((text, x, y, size, style))

    def _space(self, amount: float) -> None:
        self.y -= amount
        if self.y < self.bottom:
            self._new_page()

    def _add_wrapped(self, paragraph: str, size: float, style: str, width: int, line_height: float) -> None:
        for line in wrap_text(paragraph, width):
            if self.y < self.bottom:
                self._new_page()
            self._draw_text(line, self.margin_left, self.y, size, style)
            self.y -= line_height

    def _page_content(
        self, lines: list[tuple[str, float, float, float, str]], page_index: int, page_count: int
    ) -> bytes:
        chunks: list[bytes] = []
        if page_index == 1:
            chunks.append(b"0.88 0.72 0.28 rg\n0 810 595.28 31.89 re f\n")
        if page_index == page_count and self.source_label:
            chunks.append(b"0.55 0.55 0.55 rg\n")
            src_line = f"Fonte: {self.source_label}"
            chunks.append(f"BT /F3 8.5 Tf {self.margin_left:.2f} 58 Td ".encode())
            chunks.append(b"(" + pdf_escape(src_line) + b") Tj ET\n")
        chunks.append(b"0.12 0.12 0.12 rg\n")
        for text, x, y, size, style in lines:
            font = {"body": "F1", "bold": "F2", "italic": "F3", "title": "F4"}[style]
            escaped = pdf_escape(text)
            chunks.append(f"BT /{font} {size:.2f} Tf {x:.2f} {y:.2f} Td ".encode())
            chunks.append(b"(" + escaped + b") Tj ET\n")
        footer = f"{self.council_name} | {page_index}/{page_count}"
        chunks.append(b"0.45 0.45 0.45 rg\n")
        chunks.append(f"BT /F1 8.5 Tf {self.margin_left:.2f} 38 Td ".encode())
        chunks.append(b"(" + pdf_escape(footer) + b") Tj ET\n")
        return b"".join(chunks)


# ─── HTML document for Edge/Chrome renderer ───────────────────────────────────

def build_html_document(
    council_name: str,
    title: str,
    doc_type: str,
    source_label: str,
    paragraphs: list[str],
    lang_code: str = "pt",
) -> str:
    esc_council = html.escape(council_name)
    esc_title = html.escape(title)
    esc_type = html.escape(doc_type)
    esc_source = html.escape(source_label)
    body_parts = []
    for paragraph in paragraphs:
        kind = paragraph_kind(paragraph)
        escaped = html.escape(paragraph)
        if kind == "heading":
            body_parts.append(f"<h2>{escaped}</h2>")
        elif kind == "subheading":
            body_parts.append(f"<h3>{escaped}</h3>")
        else:
            body_parts.append(f"<p>{escaped}</p>")

    return f"""<!doctype html>
<html lang="{lang_code}">
<head>
  <meta charset="utf-8">
  <title>{esc_council} — {esc_title}</title>
  <style>
    @page {{
      size: A4;
      margin: 22mm 20mm 22mm 20mm;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      color: #1b1b1b;
      font-family: Georgia, "Times New Roman", serif;
      font-size: 11.4pt;
      line-height: 1.48;
      margin: 0;
      text-rendering: optimizeLegibility;
    }}
    .cover {{
      break-after: page;
      min-height: 245mm;
      display: flex;
      flex-direction: column;
      justify-content: center;
      text-align: center;
      border-top: 1.5pt solid #b08d2c;
      border-bottom: 1.5pt solid #b08d2c;
      padding: 18mm 7mm;
    }}
    .source {{
      color: #9a7a21;
      font-family: Arial, sans-serif;
      font-size: 10pt;
      letter-spacing: .04em;
      margin-bottom: 10mm;
    }}
    .council {{
      font-size: 14pt;
      font-variant: small-caps;
      letter-spacing: .03em;
      margin-bottom: 7mm;
    }}
    h1 {{
      font-size: 22pt;
      line-height: 1.18;
      margin: 0 0 8mm;
      overflow-wrap: anywhere;
      text-transform: uppercase;
    }}
    .doc-type {{
      font-size: 12pt;
      font-style: italic;
    }}
    .content {{
      margin: 0 auto;
      max-width: 166mm;
    }}
    .content h2 {{
      break-after: avoid;
      font-size: 14.5pt;
      line-height: 1.25;
      margin: 10mm 0 4mm;
      text-align: center;
      text-transform: uppercase;
    }}
    .content h3 {{
      break-after: avoid;
      font-size: 12.6pt;
      margin: 7mm 0 3mm;
      text-align: center;
      text-transform: uppercase;
    }}
    .content p {{
      margin: 0 0 3.4mm;
      orphans: 3;
      text-align: justify;
      widows: 3;
    }}
    .footer-source {{
      border-top: .6pt solid #d5c48d;
      color: #777;
      font-family: Arial, sans-serif;
      font-size: 8.5pt;
      margin-top: 12mm;
      padding-top: 3mm;
      text-align: center;
    }}
  </style>
</head>
<body>
  <section class="cover">
    <div class="source">Vatican.va</div>
    <div class="council">{esc_council}</div>
    <h1>{esc_title}</h1>
    <div class="doc-type">{esc_type}</div>
  </section>
  <main class="content">
    {''.join(body_parts)}
    <div class="footer-source">Fonte: {esc_source}</div>
  </main>
</body>
</html>"""


# ─── Edge/Chrome PDF renderer ─────────────────────────────────────────────────

def find_edge() -> str | None:
    candidates = [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return shutil.which("msedge") or shutil.which("chrome") or shutil.which("chromium")


def build_pdf_with_edge(
    out_path: Path,
    council_name: str,
    title: str,
    doc_type: str,
    source_label: str,
    paragraphs: list[str],
    edge_path: str,
    lang_code: str,
    html_dir: Path,
    index: int,
) -> None:
    import tempfile
    import ctypes
    # Resolve 8.3 short path to long path — Edge fails with KRYPTO~1 style paths
    _raw_tmp = os.environ.get("TEMP") or tempfile.gettempdir()
    try:
        _buf = ctypes.create_unicode_buffer(512)
        ctypes.windll.kernel32.GetLongPathNameW(_raw_tmp, _buf, 512)
        _long_tmp = _buf.value or _raw_tmp
    except Exception:
        _long_tmp = _raw_tmp
    tmp_dir = Path(_long_tmp) / "vera_council_pdfs"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    slug = f"c{index:04d}_{lang_code}"
    html_path = tmp_dir / f"{slug}.html"
    tmp_pdf   = tmp_dir / f"{slug}.pdf"
    profile_dir = tmp_dir / f"prof{index:04d}"

    html_path.write_text(
        build_html_document(council_name, title, doc_type, source_label, paragraphs, lang_code),
        encoding="utf-8",
    )
    if tmp_pdf.exists():
        tmp_pdf.unlink()

    # Invoke Edge via PowerShell to ensure a clean Windows environment
    # (direct subprocess call from Git Bash silently fails to create the PDF)
    html_uri = html_path.resolve().as_uri()
    ps_script = (
        f"& '{edge_path}' --headless --disable-gpu --no-sandbox --no-pdf-header-footer "
        f"'--print-to-pdf={tmp_pdf}' '{html_uri}'"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_script],
        capture_output=True, text=True, timeout=120,
    )
    if not tmp_pdf.exists():
        raise RuntimeError(f"Edge falhou (rc={result.returncode}): {result.stderr[-400:]}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(tmp_pdf), str(out_path))


def build_pdf_simple(
    out_path: Path,
    council_name: str,
    title: str,
    doc_type: str,
    source_label: str,
    paragraphs: list[str],
) -> None:
    pdf = SimplePDF(title=title, council_name=council_name, doc_type=doc_type, source_label=source_label)
    pdf.add_title_page()
    pdf.add_paragraphs(paragraphs)
    pdf.save(out_path)


# ─── AI translation ───────────────────────────────────────────────────────────

def translate_with_ai(text_paragraphs: list[str], source_lang: str, target_lang: str, doc_title: str) -> list[str]:
    """Translate paragraphs using Claude API. Requires ANTHROPIC_API_KEY env var."""
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic package not installed — run: pip install anthropic")

    lang_names = {
        "pt": "português", "en": "inglês", "it": "italiano",
        "la": "latim eclesiástico", "de": "alemão", "es": "espanhol", "gr": "grego antigo",
    }
    source_name = lang_names.get(source_lang, source_lang)
    target_name = lang_names.get(target_lang, target_lang)

    client = anthropic.Anthropic()
    full_text = "\n\n".join(text_paragraphs[:80])  # limit to ~80 paragraphs
    prompt = (
        f"Você é um especialista em documentos eclesiásticos. Traduza o seguinte texto de um "
        f"documento conciliar da Igreja Católica ({doc_title}) do {source_name} para o {target_name}. "
        f"Mantenha fidelidade absoluta ao conteúdo teológico. Preserve numeração de cânones, títulos e "
        f"estrutura. Retorne APENAS a tradução, um parágrafo por linha separado por linha em branco.\n\n"
        f"TEXTO ORIGINAL:\n{full_text}"
    )

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    translated = message.content[0].text
    paragraphs = [p.strip() for p in translated.split("\n\n") if p.strip()]
    return paragraphs or [translated]


# ─── Output path builder ──────────────────────────────────────────────────────

def output_path_for(
    output_dir: Path, council: Council, document: CouncilDocument, lang: str
) -> Path:
    century_dir = sanitize_path_part(f"Seculo {council.century}", max_len=60)
    council_dir = sanitize_path_part(council.folder_name, max_len=80)
    doc_dir = sanitize_path_part(document.title, max_len=80)
    filename = sanitize_path_part(f"{document.title} - {lang.upper()}", max_len=100) + ".pdf"
    return output_dir / century_dir / council_dir / doc_dir / filename


# ─── Main build logic ─────────────────────────────────────────────────────────

def process_source(
    source: LangSource,
    council: Council,
    document: CouncilDocument,
    session: requests.Session,
    output_dir: Path,
    html_dir: Path,
    edge_path: str | None,
    force: bool,
    dry_run: bool,
    doc_index: int,
) -> str:
    """Process a single language source. Returns 'ok', 'skip', or error message."""
    out_path = output_path_for(output_dir, council, document, source.lang)

    if out_path.exists() and not force:
        return "skip"

    if dry_run:
        return f"[dry] would fetch {source.url}"

    try:
        html_text = fetch_text(source.url, session, source.encoding)
        paragraphs = parse_body_paragraphs(html_text)
        if not paragraphs:
            return "no text extracted"
        if len(paragraphs) < 3:
            return f"too few paragraphs ({len(paragraphs)})"
        # Reject Portuguese files that actually contain English content
        if source.lang == "pt" and _is_english_content(paragraphs):
            return "SKIP: conteudo PT e ingles — pagina nao traduzida"

        src_label = SOURCE_LABELS.get(source.site, source.site)

        if edge_path:
            build_pdf_with_edge(
                out_path, council.display_name, document.title,
                document.doc_type, src_label, paragraphs,
                edge_path, source.lang, html_dir, doc_index,
            )
        else:
            build_pdf_simple(
                out_path, council.display_name, document.title,
                document.doc_type, src_label, paragraphs,
            )
        return "ok"
    except Exception as exc:  # noqa: BLE001
        return f"ERROR: {exc}"


def process_ai_lang(
    council: Council,
    document: CouncilDocument,
    target_lang: str,
    base_paragraphs: dict[str, list[str]],
    output_dir: Path,
    html_dir: Path,
    edge_path: str | None,
    force: bool,
    dry_run: bool,
    doc_index: int,
) -> str:
    out_path = output_path_for(output_dir, council, document, target_lang)
    if out_path.exists() and not force:
        return "skip"
    if dry_run:
        return f"[dry] would translate to {target_lang}"

    # Prefer EN as source for AI translation, fallback to PT
    source_lang = "en" if "en" in base_paragraphs else ("pt" if "pt" in base_paragraphs else None)
    if not source_lang:
        return "no base lang for AI translation"

    try:
        paragraphs = translate_with_ai(base_paragraphs[source_lang], source_lang, target_lang, document.title)
        src_label = f"Tradução Assistida por IA — base: {SOURCE_LABELS.get('ai', 'IA')}"
        if edge_path:
            build_pdf_with_edge(
                out_path, council.display_name, document.title,
                document.doc_type, src_label, paragraphs,
                edge_path, target_lang, html_dir, doc_index,
            )
        else:
            build_pdf_simple(
                out_path, council.display_name, document.title,
                document.doc_type, src_label, paragraphs,
            )
        return "ok"
    except Exception as exc:  # noqa: BLE001
        return f"AI ERROR: {exc}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gera PDFs de todos os 21 Concílios Ecumênicos."
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--council", help="Processar apenas um concílio (key, ex: vaticano-ii)")
    parser.add_argument("--lang", help="Processar apenas um idioma (ex: pt, en, la)")
    parser.add_argument("--force", action="store_true", help="Sobrescrever PDFs existentes")
    parser.add_argument("--dry-run", action="store_true", help="Mostrar o que seria gerado sem gerar")
    parser.add_argument("--ai-translate", action="store_true", help="Usar IA para idiomas sem fonte")
    parser.add_argument("--delay", type=float, default=0.5, help="Pausa entre requests (segundos)")
    parser.add_argument(
        "--renderer", choices=["auto", "edge", "simple"], default="auto",
        help="Renderer PDF: edge (melhor) ou simple (sem dependências)",
    )
    args = parser.parse_args()

    councils_to_process = COUNCILS
    if args.council:
        if args.council not in COUNCIL_BY_KEY:
            print(f"ERRO: concílio '{args.council}' não encontrado.", file=sys.stderr)
            print(f"Opções: {', '.join(COUNCIL_BY_KEY)}", file=sys.stderr)
            return 1
        councils_to_process = [COUNCIL_BY_KEY[args.council]]

    edge_path: str | None = None
    if args.renderer in {"auto", "edge"}:
        edge_path = find_edge()
    if args.renderer == "edge" and not edge_path:
        print("ERRO: Edge/Chrome não encontrado para renderer=edge.", file=sys.stderr)
        return 1
    print(f"Renderer: {'Edge/Chrome (' + edge_path + ')' if edge_path else 'SimplePDF interno'}")
    if args.dry_run:
        print("[DRY-RUN] nenhum arquivo será criado.\n")

    session = make_session()
    stats = {"ok": 0, "skip": 0, "error": 0, "dry": 0}
    doc_index = 0
    html_dir = DEFAULT_HTML_DIR

    for council in councils_to_process:
        print(f"\n{'='*60}")
        print(f"  Concílio {council.number:02d}: {council.display_name} ({council.year})")
        print(f"{'='*60}")

        for document in council.documents:
            print(f"  Documento: {document.title}")
            base_paragraphs: dict[str, list[str]] = {}
            doc_index += 1
            # Languages whose real source failed → will fall back to AI if --ai-translate
            failed_source_langs: set[str] = set()

            for source in document.sources:
                if args.lang and source.lang != args.lang:
                    continue

                result = process_source(
                    source, council, document, session,
                    args.output_dir, html_dir, edge_path,
                    args.force, args.dry_run, doc_index,
                )
                out_path = output_path_for(args.output_dir, council, document, source.lang)
                symbol = "OK" if result == "ok" else ("->" if result == "skip" else ("~" if result.startswith("[dry]") else "XX"))
                print(f"    {symbol} [{source.lang.upper()}] {result}")

                if result == "ok" and not args.dry_run:
                    stats["ok"] += 1
                    if source.lang not in base_paragraphs:
                        try:
                            html_text = fetch_text(source.url, session)
                            base_paragraphs[source.lang] = parse_body_paragraphs(html_text)
                        except Exception:
                            pass
                elif result == "skip":
                    stats["skip"] += 1
                    if source.lang not in base_paragraphs and out_path.exists():
                        base_paragraphs[source.lang] = []  # mark as available
                elif result.startswith("[dry]"):
                    stats["dry"] += 1
                else:
                    stats["error"] += 1
                    # Source failed — queue this lang for AI fallback
                    if args.ai_translate:
                        failed_source_langs.add(source.lang)

                if not args.dry_run:
                    time.sleep(args.delay)

            # AI langs = explicitly listed + langs whose real source failed
            effective_ai_langs = list(set(document.ai_langs) | failed_source_langs)
            if args.ai_translate and effective_ai_langs:
                for target_lang in effective_ai_langs:
                    if args.lang and target_lang != args.lang:
                        continue
                    result = process_ai_lang(
                        council, document, target_lang, base_paragraphs,
                        args.output_dir, html_dir, edge_path,
                        args.force, args.dry_run, doc_index,
                    )
                    symbol = "OK" if result == "ok" else ("->" if result == "skip" else ("~" if result.startswith("[dry]") else "XX"))
                    print(f"    {symbol} [{target_lang.upper()}] (IA) {result}")
                    if result == "ok":
                        stats["ok"] += 1
                    elif result == "skip":
                        stats["skip"] += 1
                    elif result.startswith("[dry]"):
                        stats["dry"] += 1
                    else:
                        stats["error"] += 1

    print(f"\n{'='*60}")
    print("  CONCLUIDO")
    print(f"  PDFs gerados : {stats['ok']}")
    print(f"  Pulados      : {stats['skip']}")
    print(f"  Erros        : {stats['error']}")
    if args.dry_run:
        print(f"  [dry] seria  : {stats['dry']}")
    print(f"{'='*60}")
    return 0 if stats["error"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
