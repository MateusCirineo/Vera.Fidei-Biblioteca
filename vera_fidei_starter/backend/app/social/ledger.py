from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
from typing import Any


class SocialLedger:
    """Registro append-only de prévias, aprovações e publicações.

    Somente eventos ``published`` entram na deduplicação. Uma prévia rejeitada
    pode ser refeita sem marcar uma citação como usada.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def events(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                rows.append(value)
        return rows

    def published_fingerprints(self) -> set[str]:
        return {
            str(event.get("source_fingerprint"))
            for event in self.events()
            if event.get("event") == "published" and event.get("source_fingerprint")
        }

    def published_remote_ids(self) -> set[str]:
        return {
            str(event.get("remote_media_id"))
            for event in self.events()
            if event.get("event") == "published" and event.get("remote_media_id")
        }

    def append(self, event: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "recorded_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            **event,
        }
        payload = (json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        fd = os.open(self.path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
        try:
            os.write(fd, payload)
        finally:
            os.close(fd)
