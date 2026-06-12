from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
from multiprocessing import Process
from pathlib import Path, PurePosixPath
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func

from models.database import Book, BookFile, Chunk, SessionLocal, init_db
from services.ingestion_service import (
    IngestionService,
    _detect_lang,
    _detect_publisher,
    _detect_translator,
    _extract_sample_pages,
)
from storage.pdf_storage import get_pdf_storage
from utils.author_detection import detect_church_document
from utils.patristic_parser import parse_patristic_book


PATRISTIC_FOLDER_KEYS = {
    "patristica paulus",
    "patrologia grega",
    "patrologia latina",
    "igreja primitiva",
    "catena aurea",
    "santo agostinho",
    "sao jeronimo",
    "sao gregorio magno",
    "santo epifanio",
    "sao clemente de alexandria",
    "santo inac io de antioquia",
    "santo inacio de antioquia",
    "sao vicente de lerins",
}

AUTHOR_BY_FOLDER = {
    "beata anne catherine emmerich": "Beata Anne Catherine Emmerich",
    "beato duns scotus": "Beato Duns Scotus",
    "hugo de sao vitor": "Hugo de Sao Vitor",
    "padre adolphe tanquerey": "Padre Adolphe Tanquerey",
    "padre gabriele amorth": "Padre Gabriele Amorth",
    "padre julio maria de lombaerde": "Padre Julio Maria de Lombaerde",
    "papa bento xvi ratzinger": "Papa Bento XVI",
    "papa francisco": "Papa Francisco",
    "santa catarina de sena": "Santa Catarina de Sena",
    "santa edith stein": "Santa Edith Stein",
    "santa hildegarda de bingen": "Santa Hildegarda de Bingen",
    "santa teresa de jesus": "Santa Teresa de Jesus",
    "santo afonso maria de ligorio": "Santo Afonso Maria de Ligorio",
    "santo agostinho": "Santo Agostinho de Hipona",
    "santo anselmo de cantuaria": "Santo Anselmo de Cantuaria",
    "santo epifanio": "Santo Epifanio",
    "santo inacio de antioquia": "Santo Inacio de Antioquia",
    "santo inacio de loyola": "Santo Inacio de Loyola",
    "santo tomas de aquino": "Santo Tomas de Aquino",
    "sao belarmino": "Sao Roberto Belarmino",
    "sao bento": "Sao Bento",
    "sao bernardo de claraval": "Sao Bernardo de Claraval",
    "sao boaventura": "Sao Boaventura",
    "sao clemente de alexandria": "Sao Clemente de Alexandria",
    "sao francisco de sales": "Sao Francisco de Sales",
    "sao gregorio magno": "Sao Gregorio Magno",
    "sao jeronimo": "Sao Jeronimo",
    "sao joao bosco dom bosco": "Sao Joao Bosco",
    "sao joao da cruz": "Sao Joao da Cruz",
    "sao joao eudes": "Sao Joao Eudes",
    "sao joao maria vianney": "Sao Joao Maria Vianney",
    "sao joao paulo ii": "Sao Joao Paulo II",
    "sao josemaria escriva": "Sao Josemaria Escriva",
    "sao leonardo de porto mauricio": "Sao Leonardo de Porto Mauricio",
    "sao luis maria grignon de montfort": "Sao Luis Maria Grignion de Montfort",
    "sao paulo vi": "Sao Paulo VI",
    "sao roberto belarmino": "Sao Roberto Belarmino",
    "sao vicente de lerins": "Sao Vicente de Lerins",
    "tomas de kempis": "Tomas de Kempis",
}

DOCTYPE_COLLECTION = {
    "concilio": "CONC",
    "bula": "MAG",
    "enciclica": "MAG",
    "constituicao_apostolica": "MAG",
    "carta_apostolica": "MAG",
    "motu_proprio": "MAG",
    "exortacao_apostolica": "MAG",
    "catecismo": "CATEQ",
    "catequese": "CATEQ",
    "liturgia": "LIT",
    "doutrina_social": "DSI",
    "direito_canonico": "CDC",
    "teologia": "TEO",
    "linguas_biblicas": "LING",
    "literatura_crista": "LITCR",
    "outro": "DOC",
}

BLOCKED_CATHOLIC_CORE_TERMS = {
    "autores protestantes",
    "protestantes",
    "protestante",
    "protestantismo",
    "reforma protestante",
    "martinho lutero",
    "luther",
    "luterano",
    "luteranismo",
    "joao calvino",
    "calvino",
    "calvinismo",
    "zwinglio",
    "zwingli",
    "melanchthon",
    "john wesley",
    "wesley",
    "evangelico",
}


def normalize(value: str | None) -> str:
    value = value or ""
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def compact_key(value: str | None) -> str:
    value = normalize(value)
    value = re.sub(r"\b(pdf|upload|direct)\b", " ", value)
    value = re.sub(r"\b\d{7,}\b", " ", value)
    roman_map = {
        "i": "1",
        "ii": "2",
        "iii": "3",
        "iv": "4",
        "v": "5",
        "vi": "6",
        "vii": "7",
        "viii": "8",
        "ix": "9",
        "x": "10",
        "xi": "11",
        "xii": "12",
        "xiii": "13",
        "xiv": "14",
        "xv": "15",
        "xvi": "16",
        "xvii": "17",
        "xviii": "18",
        "xix": "19",
        "xx": "20",
    }
    for roman, number in sorted(roman_map.items(), key=lambda item: -len(item[0])):
        value = re.sub(rf"\bsessao\s+{roman}\b", f"sessao {number}", value)
    return re.sub(r"\s+", " ", value).strip()


def field(value: str | None, limit: int = 240) -> str:
    value = re.sub(r"\s+", " ", (value or "").strip())
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "..."


def is_blocked_for_catholic_core(row: dict[str, Any]) -> bool:
    text = normalize(" ".join([
        row.get("path") or "",
        row.get("name") or "",
        row.get("top_folder") or "",
    ]))
    return any(term in text for term in BLOCKED_CATHOLIC_CORE_TERMS)


def basename(path: str) -> str:
    return PurePosixPath(path.replace("\\", "/")).name


def clean_title_from_filename(name: str) -> str:
    title = Path(name).stem
    title = title.replace("__org__", "(org.)")
    title = re.sub(r"--\s*Anna.?s Archive.*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"--\s*[0-9a-f]{16,}.*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\b[0-9a-f]{24,}\b", "", title, flags=re.IGNORECASE)
    title = title.replace("_", " ").replace("-", " ")
    title = re.sub(r"\s+", " ", title).strip(" ._-")
    return field(title or Path(name).stem)


def extract_volume(text: str) -> int | None:
    text_norm = normalize(text)
    patterns = [
        r"\bvol(?:ume)?\s*\.?\s*(\d{1,3})\b",
        r"\btomo\s*(\d{1,3})\b",
        r"\bpg\s*0*(\d{1,3})\b",
        r"\bpl\s*0*(\d{1,3})\b",
        r"\bpatristica\s+vol\s*\.?\s*(\d{1,3})\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text_norm)
        if match:
            return int(match.group(1))
    return None


def extract_year(text: str) -> int | None:
    for match in re.finditer(r"\b(1[0-9]{3}|20[0-9]{2})\b", text):
        year = int(match.group(1))
        if 1000 <= year <= 2099:
            return year
    return None


def pope_from_text(text: str) -> str | None:
    norm = normalize(text)
    patterns = [
        ("Papa Francisco", r"\b(francisco|papa francisco)\b"),
        ("Papa Bento XVI", r"\b(bento xvi|ratzinger|papa bento xvi)\b"),
        ("Papa Joao Paulo II", r"\b(joao paulo ii|jp ii|papa joao paulo ii)\b"),
        ("Papa Paulo VI", r"\b(paulo vi|papa paulo vi)\b"),
        ("Papa Joao XXIII", r"\b(joao xxiii|papa joao xxiii)\b"),
        ("Papa Pio XII", r"\b(pio xii|papa pio xii)\b"),
        ("Papa Pio XI", r"\b(pio xi|papa pio xi)\b"),
        ("Papa Pio X", r"\b(pio x\b|papa pio x\b)"),
        ("Papa Sao Pio V", r"\b(pio v\b|sao pio v\b|papa pio v\b)"),
        ("Papa Leao XIII", r"\b(leao xiii|papa leao xiii)\b"),
    ]
    for label, pattern in patterns:
        if re.search(pattern, norm):
            return label
    return None


def document_type_from_text(top_folder: str, path: str, title: str) -> str:
    text = normalize(f"{top_folder} {path} {title}")
    if any(term in text for term in ("concilio", "sinodo", "niceia", "constantinopla", "calcedonia", "trento", "vaticano ii")):
        return "concilio"
    if any(term in text for term in ("catecismo", "compendio do catecismo", "youcat")):
        return "catecismo"
    if any(term in text for term in ("catequese", "iniciacao crista", "curso elementar")):
        return "catequese"
    if any(term in text for term in ("liturgia", "missal", "ritual", "rito", "breviario", "cerimonial", "sacrament", "exorcismo", "bencao", "bencoes", "indulgencia")):
        return "liturgia"
    if any(term in text for term in ("codigo de direito canonico", "direito canonico", "cdc", "codex iuris canonici")):
        return "direito_canonico"
    if any(term in text for term in ("doutrina social", "compendio da doutrina social")):
        return "doutrina_social"
    if any(term in text for term in ("enciclica", "quadragesimo", "rerum novarum", "humanae vitae", "fides et ratio")):
        return "enciclica"
    if "bula" in text:
        return "bula"
    if "motu proprio" in text:
        return "motu_proprio"
    if "exortacao apostolica" in text:
        return "exortacao_apostolica"
    if any(term in text for term in ("constituicao apostolica", "constitutio apostolica")):
        return "constituicao_apostolica"
    if any(term in text for term in ("carta apostolica", "epistola apostolica")):
        return "carta_apostolica"
    if any(term in text for term in ("grego", "hebraico", "latim", "koine", "lexico", "dicionario", "enciclopedia", "manuscritos do mar morto", "canon biblico")):
        return "linguas_biblicas"
    if any(term in text for term in ("vida dos santos", "devocionario", "oracao", "rosario", "paixao de cristo", "aparicoes", "milagres", "espiritualidade", "poesia")):
        return "literatura_crista"
    return "teologia"


def known_document_override(text: str) -> dict[str, Any] | None:
    norm = normalize(text)
    if "quo primum" in norm:
        return {
            "title": "Quo Primum Tempore",
            "author": "Papa Sao Pio V",
            "pope": "Papa Sao Pio V",
            "document_type": "bula",
            "collection": "MAG",
            "document_year": 1570,
            "edition_label": "Magisterio pontificio",
        }
    if "summorum pontificum" in norm:
        return {
            "title": "Summorum Pontificum",
            "author": "Papa Bento XVI",
            "pope": "Papa Bento XVI",
            "document_type": "motu_proprio",
            "collection": "MAG",
            "document_year": 2007,
            "edition_label": "Magisterio pontificio",
        }
    if "traditionis custodes" in norm:
        return {
            "title": "Traditionis Custodes",
            "author": "Papa Francisco",
            "pope": "Papa Francisco",
            "document_type": "motu_proprio",
            "collection": "MAG",
            "document_year": 2021,
            "edition_label": "Magisterio pontificio",
        }
    if "missale romanum" in norm:
        return {
            "title": "Missale Romanum",
            "author": "Papa Paulo VI",
            "pope": "Papa Paulo VI",
            "document_type": "constituicao_apostolica",
            "collection": "MAG",
            "document_year": 1969,
            "edition_label": "Magisterio pontificio",
        }
    return None


def is_patristic_folder(top_folder: str, path: str, parsed_tradition: str | None) -> bool:
    top = normalize(top_folder)
    all_text = normalize(f"{top_folder} {path}")
    if top in PATRISTIC_FOLDER_KEYS:
        return True
    if any(term in all_text for term in ("patristica", "patrologia", "padres apostolicos", "didaque")):
        return True
    return parsed_tradition is not None and any(
        term in all_text
        for term in ("agostinho", "jeronimo", "crisostomo", "irineu", "origenes", "atanasio", "ambrosio", "basilio", "gregorio")
    )


def patristic_tradition_for(top_folder: str, path: str, parsed_tradition: str | None, language: str | None = None) -> str:
    text = normalize(f"{top_folder} {path}")
    lang = normalize(language)
    if "patrologia grega" in text or re.search(r"\bpg\s*0*\d+", text):
        return "grega"
    if "patrologia latina" in text or re.search(r"\bpl\s*0*\d+", text):
        return "latina"
    if "oriental" in text:
        return "oriental"
    if "paulus" in text or "portugues" in text or "portuguese" in text or lang in {"pt", "por", "portugues", "portuguese"}:
        return "portuguesa"
    return parsed_tradition or "portuguesa"


def patristic_collection(top_folder: str, path: str, tradition: str) -> str | None:
    text = normalize(f"{top_folder} {path}")
    if "patrologia grega" in text or re.search(r"\bpg\s*0*\d+", text):
        return "PG"
    if "patrologia latina" in text or re.search(r"\bpl\s*0*\d+", text):
        return "PL"
    if tradition == "portuguesa":
        return "PT"
    return None


def edition_for(top_folder: str, path: str, section: str, doctype: str | None, detected_publisher: str | None) -> str:
    text = normalize(f"{top_folder} {path}")
    if "patristica paulus" in text or detected_publisher == "Paulus":
        return "Paulus"
    if "patrologia grega" in text or re.search(r"\bpg\s*0*\d+", text):
        return "Migne PG"
    if "patrologia latina" in text or re.search(r"\bpl\s*0*\d+", text):
        return "Migne PL"
    if detected_publisher:
        return detected_publisher
    if section == "patristica":
        return "Outras editoras"
    if section == "documentos" and doctype in {"enciclica", "bula", "constituicao_apostolica", "carta_apostolica", "motu_proprio", "exortacao_apostolica"}:
        return "Magisterio pontificio"
    return ""


def author_from_folder(top_folder: str) -> str | None:
    key = normalize(top_folder)
    if key in AUTHOR_BY_FOLDER:
        return AUTHOR_BY_FOLDER[key]
    if re.match(r"^(santo|santa|sao|beato|beata|padre|papa)\b", key):
        return field(top_folder, 120)
    return None


def is_primary_source(section: str, doctype: str | None, author: str, top_folder: str, title: str) -> bool:
    text = normalize(f"{top_folder} {title} {author}")
    if section == "patristica":
        return True
    if doctype in {
        "concilio",
        "bula",
        "enciclica",
        "constituicao_apostolica",
        "carta_apostolica",
        "motu_proprio",
        "exortacao_apostolica",
        "catecismo",
        "liturgia",
        "direito_canonico",
    }:
        return True
    if re.search(r"\b(santo|santa|sao|beato|beata|papa)\b", text):
        return True
    return False


def build_metadata(row: dict[str, Any], pdf_path: Path) -> dict[str, Any]:
    source_path = row.get("path") or row.get("name") or ""
    name = row.get("name") or basename(source_path)
    top_folder = row.get("top_folder") or (source_path.split("/", 1)[0] if "/" in source_path else "")
    raw_title = clean_title_from_filename(name)

    sample_pages = _extract_sample_pages(str(pdf_path), n=8)
    sample_text = "\n".join(page.get("text", "") for page in sample_pages if isinstance(page, dict))
    metadata_text = f"{raw_title}\n{top_folder}\n{sample_text[:4000]}"
    parsed = parse_patristic_book(metadata_text)
    church_meta = detect_church_document(raw_title, sample_text[:1000])

    detected_publisher = parsed.publisher or _detect_publisher(sample_text)
    detected_translator = _detect_translator(sample_text)
    language = parsed.language or _detect_lang(sample_text)
    year = extract_year(f"{source_path} {sample_text[:500]}")
    volume = extract_volume(f"{source_path} {raw_title}")
    doc_override = known_document_override(f"{top_folder} {source_path} {raw_title} {sample_text[:500]}")

    if doc_override:
        title = doc_override["title"]
        author = doc_override["author"]
        section = "documentos"
        doctype = doc_override["document_type"]
        tradition = None
        collection = doc_override["collection"]
        canonical_author = author
        canonical_title = title
        edition_label = doc_override["edition_label"]
        year = doc_override["document_year"] or year
    elif church_meta:
        title = church_meta["canonical_title"] or raw_title
        author = church_meta["author"]
        section = church_meta["library_section"]
        doctype = church_meta["document_type"]
        tradition = None
        collection = church_meta["collection"]
        canonical_author = church_meta.get("canonical_author") or author
        canonical_title = church_meta.get("canonical_title") or title
        edition_label = church_meta.get("edition_label") or edition_for(top_folder, source_path, section, doctype, detected_publisher)
    elif is_patristic_folder(top_folder, source_path, parsed.patristic_tradition):
        tradition = patristic_tradition_for(top_folder, source_path, parsed.patristic_tradition, language)
        section = "patristica"
        doctype = None
        collection = patristic_collection(top_folder, source_path, tradition)
        title = parsed.canonical_title or raw_title
        author = parsed.author or author_from_folder(top_folder) or "Autor desconhecido"
        canonical_author = parsed.canonical_author or author
        canonical_title = parsed.canonical_title or title
        edition_label = edition_for(top_folder, source_path, section, doctype, detected_publisher)
    else:
        doctype = document_type_from_text(top_folder, source_path, raw_title)
        section = "documentos"
        tradition = None
        collection = DOCTYPE_COLLECTION.get(doctype, "DOC")
        title = raw_title
        folder_author = author_from_folder(top_folder)
        pope = pope_from_text(f"{top_folder} {source_path} {raw_title}")
        if pope and doctype == "teologia":
            doctype = "outro"
            collection = DOCTYPE_COLLECTION[doctype]
        author = parsed.author or folder_author or pope or "Autor desconhecido"
        canonical_author = parsed.canonical_author or folder_author or pope or author
        canonical_title = parsed.canonical_title or title
        edition_label = edition_for(top_folder, source_path, section, doctype, detected_publisher)

    pope = doc_override.get("pope") if doc_override else pope_from_text(f"{top_folder} {source_path} {raw_title}")
    if section == "documentos" and pope is None:
        pope = pope_from_text(author)

    if not detected_translator and detected_publisher:
        detected_translator = f"{detected_publisher} Editora" if not detected_publisher.lower().endswith("editora") else detected_publisher

    if edition_label in {"Migne PG", "Migne PL"}:
        if edition_label == "Migne PG":
            language = "latim/grego"
        elif edition_label == "Migne PL":
            language = "latim"

    return {
        "collection": collection,
        "title": field(title),
        "author": field(author or "Autor desconhecido"),
        "language": field(language or "pt", 50),
        "edition_label": field(edition_label, 180),
        "source_label": field(f"Google Drive - {top_folder}", 180),
        "is_primary_source": is_primary_source(section, doctype, author or "", top_folder, title),
        "library_section": section,
        "patristic_tradition": tradition,
        "document_type": doctype,
        "canonical_author": field(canonical_author, 240) if canonical_author else None,
        "canonical_title": field(canonical_title, 240) if canonical_title else None,
        "pope": field(pope, 180) if pope else None,
        "document_year": year,
        "volume_number": volume,
        "editor": field(detected_publisher, 180) if detected_publisher else None,
        "translator": field(detected_translator, 180) if detected_translator else None,
    }


def load_rows(path: Path, actions: set[str], only_folder: str | None, start_after_path: str | None) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("rows", payload if isinstance(payload, list) else [])
    if not isinstance(rows, list):
        raise ValueError("analysis JSON must contain a 'rows' list")

    start_seen = start_after_path is None
    selected: list[dict[str, Any]] = []
    only_folder_norm = normalize(only_folder) if only_folder else None
    for row in rows:
        row_path = row.get("path") or row.get("name") or ""
        if not start_seen:
            if row_path == start_after_path:
                start_seen = True
            continue
        if row.get("action") not in actions:
            continue
        if only_folder_norm and normalize(row.get("top_folder")) != only_folder_norm:
            continue
        selected.append(row)
    selected.sort(key=lambda item: (normalize(item.get("top_folder")), normalize(item.get("path"))))
    return selected


def existing_keys() -> tuple[set[str], set[str]]:
    with SessionLocal() as db:
        names = {
            compact_key(row.original_filename)
            for row in db.query(BookFile.original_filename).all()
            if row.original_filename
        }
        titles = {
            compact_key(row.title)
            for row in db.query(Book.title).all()
            if row.title
        }
    return names, titles


def chunk_count(book_id: int) -> int:
    with SessionLocal() as db:
        return db.query(func.count(Chunk.id)).filter(Chunk.book_id == book_id).scalar() or 0


def book_status(book_id: int) -> tuple[str | None, str | None]:
    with SessionLocal() as db:
        book = db.get(Book, book_id)
        if book is None:
            return None, "book deleted"
        return book.ingest_status, book.ingest_error


def log_event(log_path: Path | None, event: dict[str, Any]) -> None:
    event = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), **event}
    line = json.dumps(event, ensure_ascii=False)
    print(line, flush=True)
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def run_rclone_copyto(rclone_bin: str, remote: str, source_folder_id: str, source_path: str, dest: Path, timeout: int) -> None:
    cmd = [
        rclone_bin,
        "copyto",
        "--drive-root-folder-id",
        source_folder_id,
        f"{remote}:{source_path}",
        str(dest),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=timeout)


def create_book_and_file(meta: dict[str, Any], original_filename: str, local_pdf: Path) -> tuple[int, int]:
    with SessionLocal() as db:
        book = Book(
            collection=meta["collection"],
            title=meta["title"],
            author=meta["author"],
            language=meta["language"],
            edition_label=meta["edition_label"],
            source_label=meta["source_label"],
            is_primary_source=meta["is_primary_source"],
            library_section=meta["library_section"],
            patristic_tradition=meta["patristic_tradition"],
            document_type=meta["document_type"],
            canonical_author=meta["canonical_author"],
            canonical_title=meta["canonical_title"],
            pope=meta["pope"],
            document_year=meta["document_year"],
            volume_number=meta["volume_number"],
            ingest_status="processing",
            ingest_error=None,
        )
        db.add(book)
        db.commit()
        db.refresh(book)

        book_file = BookFile(
            book_id=book.id,
            original_filename=field(original_filename, 240),
            stored_path=str(local_pdf),
            volume_number=meta["volume_number"],
            editor=meta["editor"],
            translator=meta["translator"],
        )
        db.add(book_file)
        db.commit()
        db.refresh(book_file)
        return book.id, book_file.id


def upload_and_update_file(book_id: int, file_id: int, original_filename: str, local_pdf: Path) -> str:
    storage = get_pdf_storage()
    if storage.is_remote:
        stored = storage.upload_existing_pdf(book_id, file_id, original_filename, str(local_pdf))
    else:
        stored = storage.save_pdf(book_id, original_filename, local_pdf.read_bytes())

    with SessionLocal() as db:
        book_file = db.get(BookFile, file_id)
        if book_file is None:
            raise RuntimeError(f"BookFile {file_id} disappeared")
        book_file.stored_path = stored.stored_path
        db.commit()
    return stored.stored_path


def delete_book_quietly(service: IngestionService, book_id: int) -> None:
    try:
        service.delete_book(book_id)
    except Exception as exc:
        print(f"[cleanup] could not delete failed book_id={book_id}: {exc}", flush=True)


def _ingest_worker(book_id: int, file_id: int, stored_path: str) -> None:
    IngestionService()._ingest_background(book_id, file_id, stored_path)


def run_ingest_with_timeout(
    book_id: int,
    file_id: int,
    stored_path: str,
    timeout_seconds: int,
) -> tuple[bool, str]:
    if timeout_seconds <= 0:
        IngestionService()._ingest_background(book_id, file_id, stored_path)
        return True, "completed"

    process = Process(target=_ingest_worker, args=(book_id, file_id, stored_path), daemon=False)
    process.start()
    process.join(timeout_seconds)
    if process.is_alive():
        process.terminate()
        process.join(10)
        if process.is_alive():
            process.kill()
            process.join(10)
        return False, f"timeout after {timeout_seconds}s"
    if process.exitcode not in (0, None):
        return False, f"worker exit code {process.exitcode}"
    return True, "completed"


def import_rows(args: argparse.Namespace) -> int:
    init_db()
    actions = {item.strip() for item in args.actions.split(",") if item.strip()}
    rows = load_rows(Path(args.analysis_json), actions, args.only_folder, args.start_after_path)
    if args.include_re:
        rows = [
            row for row in rows
            if args.include_re.search(row.get("path") or row.get("name") or "")
        ]
    if args.exclude_re:
        rows = [
            row for row in rows
            if not args.exclude_re.search(row.get("path") or row.get("name") or "")
        ]
    if args.limit:
        rows = rows[: args.limit]

    log_path = Path(args.log) if args.log else None
    imported = skipped = errors = 0

    log_event(log_path, {"event": "start", "rows": len(rows), "actions": sorted(actions), "dry_run": args.dry_run})
    existing_names, existing_titles = existing_keys()

    with tempfile.TemporaryDirectory(prefix="vera_drive_import_") as tmpdir:
        tmp_root = Path(tmpdir)
        for index, row in enumerate(rows, start=1):
            source_path = row.get("path") or row.get("name") or ""
            name = row.get("name") or basename(source_path)
            name_key = compact_key(name)
            title_key = compact_key(clean_title_from_filename(name))

            if args.include_re and not args.include_re.search(source_path):
                skipped += 1
                log_event(log_path, {"event": "skip_not_in_include_filter", "index": index, "path": source_path, "name": name})
                continue

            if args.exclude_re and args.exclude_re.search(source_path):
                skipped += 1
                log_event(log_path, {"event": "skip_excluded", "index": index, "path": source_path, "name": name})
                continue

            if args.catholic_core_only and is_blocked_for_catholic_core(row):
                skipped += 1
                log_event(log_path, {"event": "skip_non_catholic_core", "index": index, "path": source_path, "name": name})
                continue

            if args.max_size_mb > 0 and (row.get("size") or 0) > args.max_size_mb * 1024 * 1024:
                skipped += 1
                log_event(
                    log_path,
                    {
                        "event": "skip_too_large",
                        "index": index,
                        "path": source_path,
                        "name": name,
                        "size": row.get("size") or 0,
                        "max_size_mb": args.max_size_mb,
                    },
                )
                continue

            if name_key in existing_names or title_key in existing_titles:
                skipped += 1
                log_event(log_path, {"event": "skip_duplicate", "index": index, "path": source_path, "name": name})
                continue

            if args.dry_run:
                log_event(log_path, {"event": "dry_run", "index": index, "path": source_path, "name": name, "top_folder": row.get("top_folder")})
                continue

            safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)[:180] or f"{index}.pdf"
            local_pdf = tmp_root / f"{index:05d}_{safe_name}"
            book_id = file_id = None
            try:
                log_event(log_path, {"event": "download_start", "index": index, "path": source_path, "size": row.get("size")})
                run_rclone_copyto(args.rclone_bin, args.remote, args.source_folder_id, source_path, local_pdf, args.rclone_timeout)

                meta = build_metadata(row, local_pdf)
                meta_title_key = compact_key(meta["title"])
                if meta_title_key in existing_titles:
                    skipped += 1
                    log_event(log_path, {"event": "skip_duplicate_title", "index": index, "path": source_path, "title": meta["title"]})
                    continue

                book_id, file_id = create_book_and_file(meta, name, local_pdf)
                stored_path = upload_and_update_file(book_id, file_id, name, local_pdf)
                log_event(
                    log_path,
                    {
                        "event": "ingest_start",
                        "index": index,
                        "book_id": book_id,
                        "file_id": file_id,
                        "title": meta["title"],
                        "author": meta["author"],
                        "section": meta["library_section"],
                        "doctype": meta["document_type"],
                        "tradition": meta["patristic_tradition"],
                        "stored_path": stored_path,
                    },
                )

                completed, reason = run_ingest_with_timeout(book_id, file_id, stored_path, args.ingest_timeout)
                status, error = book_status(book_id)
                chunks = chunk_count(book_id)
                if completed and status == "done" and chunks > 0:
                    imported += 1
                    existing_names.add(name_key)
                    existing_titles.add(meta_title_key)
                    log_event(log_path, {"event": "ingest_done", "index": index, "book_id": book_id, "chunks": chunks})
                else:
                    errors += 1
                    log_event(log_path, {"event": "ingest_error", "index": index, "book_id": book_id, "status": status, "chunks": chunks, "reason": reason, "error": error})
                    if args.delete_errors and book_id is not None:
                        delete_book_quietly(IngestionService(), book_id)
                        log_event(log_path, {"event": "deleted_error_book", "index": index, "book_id": book_id})

            except subprocess.CalledProcessError as exc:
                errors += 1
                detail = (exc.stderr or exc.stdout or str(exc))[-1000:]
                log_event(log_path, {"event": "rclone_error", "index": index, "path": source_path, "error": detail})
                if args.delete_errors and book_id is not None:
                    delete_book_quietly(IngestionService(), book_id)
            except Exception as exc:
                errors += 1
                log_event(log_path, {"event": "error", "index": index, "path": source_path, "book_id": book_id, "error": str(exc)})
                if args.delete_errors and book_id is not None:
                    delete_book_quietly(IngestionService(), book_id)
            finally:
                try:
                    local_pdf.unlink(missing_ok=True)
                except OSError:
                    pass

    log_event(log_path, {"event": "finish", "imported": imported, "skipped": skipped, "errors": errors})
    return 0 if errors == 0 else 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Import selected PDFs from a Google Drive inventory into Vera.Fidei.")
    parser.add_argument("analysis_json", help="JSON created by analyze_drive_import_inventory.py")
    parser.add_argument("--source-folder-id", required=True, help="Google Drive source folder id")
    parser.add_argument("--remote", default=os.environ.get("GDRIVE_REMOTE", "vera_drive"))
    parser.add_argument("--actions", default="importar", help="Comma-separated inventory actions to import")
    parser.add_argument("--only-folder", default=None, help="Restrict import to one top folder")
    parser.add_argument("--start-after-path", default=None, help="Resume after this source path")
    parser.add_argument("--limit", type=int, default=0, help="Maximum rows to process")
    parser.add_argument("--log", default="/tmp/vera_drive_import.jsonl")
    parser.add_argument("--include-regex", default="", help="Only import source paths matching this regex")
    parser.add_argument("--exclude-regex", default="", help="Skip source paths matching this regex")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--delete-errors", action="store_true", help="Remove books created by this run if ingestion fails")
    parser.add_argument("--catholic-core-only", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--ingest-timeout", type=int, default=1800, help="Maximum seconds to spend extracting/indexing one PDF; 0 disables timeout")
    parser.add_argument("--max-size-mb", type=int, default=0, help="Skip PDFs larger than this size in MiB; 0 disables size filtering")
    parser.add_argument("--rclone-bin", default=os.environ.get("RCLONE_BIN", "rclone"))
    parser.add_argument("--rclone-timeout", type=int, default=int(os.environ.get("VERA_RCLONE_TIMEOUT", "900")))
    args = parser.parse_args()
    args.include_re = re.compile(args.include_regex, re.IGNORECASE) if args.include_regex else None
    args.exclude_re = re.compile(args.exclude_regex, re.IGNORECASE) if args.exclude_regex else None
    return import_rows(args)


if __name__ == "__main__":
    raise SystemExit(main())
