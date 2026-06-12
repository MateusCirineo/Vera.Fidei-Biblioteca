from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.database import Book, BookFile, SessionLocal


CORE_FOLDERS = {
    "Apologética",
    "Apostolado e Evangelização",
    "Aparições e Milagres Marianos",
    "Beata Anne Catherine Emmerich",
    "Beato Duns Scotus",
    "Bíblia e Comentários",
    "Breviários",
    "Catecismos e Catequese Elementar",
    "Catena Aurea",
    "Cânon Bíblico",
    "Demonologia e Angelologia",
    "Devocionários",
    "Dicionário | Enciclopédia | Léxico",
    "Documentos da Igreja",
    "Dogmática",
    "Espiritualidade e Vida Cristã",
    "Filosofia e Teologia Moral",
    "Formação Pastoral e Direção Espiritual",
    "Hugo de São Vítor",
    "Igreja Primitiva",
    "Manuscritos do Mar Morto",
    "Milagres",
    "Oração",
    "Padre Adolphe Tanquerey",
    "Padre Gabriele Amorth",
    "Padre Júlio Maria de Lombaerde",
    "Paixão de Cristo",
    "Papa Bento XVI (Ratzinger)",
    "Papa Francisco",
    "Patrologia Grega",
    "Patrologia Latina",
    "Patrística Paulus",
    "Ritos",
    "Sacerdócio",
    "Sacramentos",
    "Santa Catarina de Sena",
    "Santa Edith Stein",
    "Santa Hildegarda de Bingen",
    "Santa Teresa de Jesus",
    "Santíssimo Rosário",
    "Santo Afonso Maria de Ligório",
    "Santo Agostinho",
    "Santo Anselmo de Cantuária",
    "Santo Epifânio",
    "Santo Inácio de Antioquia",
    "Santo Inácio de Loyola",
    "Santo Tomás de Aquino",
    "São Belarmino",
    "São Bento",
    "São Bernardo de Claraval",
    "São Boaventura",
    "São Clemente de Alexandria",
    "São Francisco de Sales",
    "São Gregório Magno",
    "São Jerônimo",
    "São João Bosco (Dom Bosco)",
    "São João da Cruz",
    "São João Eudes",
    "São João Maria Vianney",
    "São João Paulo II",
    "São Josemaria Escrivá",
    "São Leonardo de Porto Maurício",
    "São Luis Maria Grignon de Montfort",
    "São Paulo VI",
    "São Roberto Belarmino",
    "São Vicente de Lérins",
    "Teologia",
    "Teologia Dogmática",
    "Tomás de Kempis",
    "Vida dos Santos",
}

REVIEW_FOLDERS = {
    "01 - Ainda Desorganizado",
    "Autores Protestantes",
    "Biografias",
    "Biologia e Catolicismo",
    "Cisma PseudoTradicionalista",
    "Conservadorismo",
    "Curso de Teologia Católica e Bíblia",
    "Daniel Rops",
    "Filosofia",
    "Flávio Josefo",
    "Fulton Sheen",
    "G.K. Chesterton",
    "História",
    "Livros em Inglês",
    "Nazismo e a Igreja",
    "Organizações Secretas",
    "Outros",
    "Padre Quevedo",
    "Peter Kreeft",
    "Professor Felipe Aquino",
    "Protestantes",
    "Scott Hahn",
    "Trivium e Quadrivium",
    "Vozes em Defesa da Fé",
}

SKIP_FOLDERS = {
    "Alfabetização",
    "Aristóteles",
    "Ateísmo",
    "Culinária",
    "Dr. Kappas",
    "Economia e Libertarianismo",
    "Gustavo Barroso",
    "Homero",
    "Olavo de Carvalho",
    "Roger Scruton",
    "Tolkien",
    "Trabalhos Academicos",
}


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower()
    value = re.sub(r"\.[a-z0-9]{1,8}$", "", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    value = re.sub(r"\b(pdf|upload|direct)\b", " ", value)
    value = re.sub(r"\b\d{7,}\b", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def classify_folder(top_folder: str) -> str:
    if top_folder in CORE_FOLDERS:
        return "importar"
    if top_folder in REVIEW_FOLDERS:
        return "revisar"
    if top_folder in SKIP_FOLDERS:
        return "pular"
    return "revisar"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("inventory_json")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    data = json.loads(Path(args.inventory_json).read_text(encoding="utf-8"))
    pdfs = [
        item for item in data
        if (item.get("Path") or item.get("Name") or "").lower().endswith(".pdf")
    ]

    with SessionLocal() as db:
        existing_names = {
            normalize(row.original_filename)
            for row in db.query(BookFile.original_filename).all()
            if row.original_filename
        }
        existing_titles = {
            normalize(row.title)
            for row in db.query(Book.title).all()
            if row.title
        }

    rows = []
    stats: dict[str, dict[str, int]] = {}
    for item in pdfs:
        path = item.get("Path") or item.get("Name") or ""
        name = os.path.basename(path)
        top = path.split("/", 1)[0] if "/" in path else "<root>"
        action = classify_folder(top)
        norm_name = normalize(name)
        duplicate = norm_name in existing_names or norm_name in existing_titles
        if duplicate:
            action = "duplicado"

        rows.append({
            "path": path,
            "name": name,
            "top_folder": top,
            "size": item.get("Size") or 0,
            "action": action,
            "duplicate": duplicate,
        })

        bucket = stats.setdefault(action, {"files": 0, "bytes": 0})
        bucket["files"] += 1
        bucket["bytes"] += item.get("Size") or 0

    top_stats: dict[str, dict[str, int]] = {}
    for row in rows:
        bucket = top_stats.setdefault(row["top_folder"], {"files": 0, "bytes": 0})
        bucket["files"] += 1
        bucket["bytes"] += row["size"]

    result = {
        "total_pdfs": len(rows),
        "total_bytes": sum(row["size"] for row in rows),
        "stats": stats,
        "top_folders": [
            {"folder": folder, **values}
            for folder, values in sorted(top_stats.items(), key=lambda item: (-item[1]["files"], item[0]))
        ],
        "rows": rows,
    }

    if args.out:
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({k: result[k] for k in ("total_pdfs", "total_bytes", "stats")}, ensure_ascii=False, indent=2))
    print("Top folders:")
    for item in result["top_folders"][:40]:
        print(f"{item['files']:4d}  {item['bytes'] / (1024 ** 3):7.2f} GB  {item['folder']}")

    print("Sample importar:")
    for row in [r for r in rows if r["action"] == "importar"][:30]:
        print("  ", row["path"])

    print("Sample revisar:")
    for row in [r for r in rows if r["action"] == "revisar"][:30]:
        print("  ", row["path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
