import re

CHUNK_SIZE = 500     # palavras por chunk
CHUNK_OVERLAP = 100  # sobreposição entre chunks


class Chunker:
    def chunk(self, pages: list[dict], document_meta: dict) -> list[dict]:
        full_text, page_offsets = self._build_full_text(pages)
        column_markers = self._detect_columns(full_text)
        return self._split(full_text, page_offsets, column_markers, document_meta)

    def _build_full_text(self, pages: list[dict]) -> tuple[str, list[dict]]:
        full_text = ""
        offsets = []
        for page in pages:
            offsets.append({"page": page["page_number"], "offset": len(full_text)})
            full_text += page["text"] + "\n"
        return full_text, offsets

    def _detect_columns(self, text: str) -> list[dict]:
        """Detecta marcadores de coluna Migne: [503], col. 503"""
        pattern = r'\[(\d{3,4})\]|col\.\s*(\d{3,4})'
        markers = []
        for m in re.finditer(pattern, text, flags=re.IGNORECASE):
            col = int(m.group(1) or m.group(2))
            markers.append({"column": col, "position": m.start()})
        return markers

    def _split(self, full_text: str, page_offsets: list[dict], column_markers: list[dict], meta: dict) -> list[dict]:
        words = full_text.split()
        step = CHUNK_SIZE - CHUNK_OVERLAP
        chunks = []

        for i in range(0, len(words), step):
            chunk_words = words[i: i + CHUNK_SIZE]
            if not chunk_words:
                break

            text = re.sub(r'\s+', ' ', " ".join(chunk_words)).strip()
            char_start = full_text.find(chunk_words[0])
            char_end = char_start + len(text)

            page_num = 1
            for po in page_offsets:
                if po["offset"] <= char_start:
                    page_num = po["page"]

            col_start = 0
            for marker in column_markers:
                if marker["position"] <= char_start:
                    col_start = marker["column"]

            chunks.append({
                **meta,
                "text": text,
                "pdf_page": page_num,
                "char_offset_start": char_start,
                "char_offset_end": char_end,
                "column_start": col_start,
                "column_end": col_start,
            })

        return chunks
