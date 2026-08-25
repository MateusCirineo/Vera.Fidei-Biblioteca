from __future__ import annotations

import io
import json
from unittest.mock import MagicMock

import pytest

from storage.pdf_storage import PdfStorage


def _storage(monkeypatch: pytest.MonkeyPatch, tmp_path) -> PdfStorage:
    monkeypatch.setenv("PDF_STORAGE", "gdrive")
    monkeypatch.setattr("storage.pdf_storage.PDF_DIR", tmp_path / "pdfs")
    monkeypatch.setattr("storage.pdf_storage.PDF_CACHE_DIR", tmp_path / "cache")
    return PdfStorage()


def test_uncached_gdrive_range_does_not_download_whole_pdf(monkeypatch, tmp_path):
    storage = _storage(monkeypatch, tmp_path)
    monkeypatch.setattr(storage, "remote_size", lambda _path: 1_000_000)
    monkeypatch.setattr(
        storage,
        "resolve_for_processing",
        lambda _path: pytest.fail("viewer must not download the full remote PDF"),
    )
    monkeypatch.setattr(storage, "_iter_gdrive_range", lambda key, start, count: iter([b"%PDF-test"]))

    response = storage.response_for_pdf(
        "gdrive://vera-fidei/pdfs/test.pdf",
        "test.pdf",
        stream_pdf=True,
        range_header="bytes=0-65535",
    )

    assert response.status_code == 206
    assert response.headers["content-length"] == "65536"
    assert response.headers["content-range"] == "bytes 0-65535/1000000"
    assert response.headers["accept-ranges"] == "bytes"


def test_gdrive_suffix_range(monkeypatch, tmp_path):
    storage = _storage(monkeypatch, tmp_path)
    monkeypatch.setattr(storage, "remote_size", lambda _path: 1000)
    captured: dict[str, int | str] = {}

    def fake_iter(key: str, start: int, count: int):
        captured.update(key=key, start=start, count=count)
        return iter([b"x" * count])

    monkeypatch.setattr(storage, "_iter_gdrive_range", fake_iter)
    response = storage.response_for_pdf(
        "gdrive://vera-fidei/pdfs/test.pdf",
        "test.pdf",
        range_header="bytes=-100",
    )

    assert response.status_code == 206
    assert captured == {"key": "vera-fidei/pdfs/test.pdf", "start": 900, "count": 100}


def test_gdrive_stream_uses_rclone_offset_and_count(monkeypatch, tmp_path):
    storage = _storage(monkeypatch, tmp_path)
    process = MagicMock()
    process.stdout = io.BytesIO(b"%PDF-1234")
    process.stderr = io.BytesIO()
    process.wait.return_value = 0
    process.poll.return_value = 0
    popen = MagicMock(return_value=process)
    monkeypatch.setattr("storage.pdf_storage.subprocess.Popen", popen)

    assert b"".join(storage._iter_gdrive_range("path/file.pdf", 10, 9)) == b"%PDF-1234"
    popen.assert_called_once_with(
        [
            storage.rclone_bin,
            "cat",
            "vera_drive:path/file.pdf",
            "--offset",
            "10",
            "--count",
            "9",
        ],
        stdout=-1,
        stderr=-1,
    )


def test_gdrive_remote_size_uses_direct_stat_and_caches(monkeypatch, tmp_path):
    storage = _storage(monkeypatch, tmp_path)
    result = MagicMock(stdout=json.dumps({"Size": 12_345}))
    run_rclone = MagicMock(return_value=result)
    monkeypatch.setattr(storage, "_run_rclone", run_rclone)

    path = "gdrive://vera-fidei/pdfs/library/test.pdf"
    assert storage.remote_size(path) == 12_345
    assert storage.remote_size(path) == 12_345
    run_rclone.assert_called_once_with(
        "lsjson",
        "vera_drive:vera-fidei/pdfs/library/test.pdf",
        "--stat",
        "--no-modtime",
    )
