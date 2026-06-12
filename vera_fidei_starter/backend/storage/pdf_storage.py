from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from fastapi import HTTPException
from fastapi.responses import FileResponse, RedirectResponse, Response, StreamingResponse


PDF_DIR = Path(
    os.environ.get("PDF_DIR")
    or Path(__file__).resolve().parents[1] / "pdfs"
).resolve()

PDF_CACHE_DIR = Path(
    os.environ.get("PDF_CACHE_DIR")
    or Path(os.environ.get("TMPDIR", "/tmp")) / "vera_fidei_pdf_cache"
)


@dataclass(frozen=True)
class StoredPdf:
    stored_path: str
    local_path: str
    storage_backend: str


def _sanitize_filename(name: str) -> str:
    cleaned = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", cleaned).strip("._-")
    cleaned = cleaned or "documento.pdf"
    if len(cleaned) <= 180:
        return cleaned
    stem, suffix = os.path.splitext(cleaned)
    suffix = suffix[:12]
    return f"{stem[: max(1, 180 - len(suffix))]}{suffix}"


def _content_disposition(original_filename: str) -> str:
    cleaned = original_filename.replace('"', "'")
    ascii_name = (
        unicodedata.normalize("NFKD", cleaned)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    ascii_name = re.sub(r"[^A-Za-z0-9._() -]+", "_", ascii_name).strip()
    if not ascii_name:
        ascii_name = "documento.pdf"
    encoded_name = quote(cleaned, safe="")
    return f'inline; filename="{ascii_name}"; filename*=UTF-8\'\'{encoded_name}'


def _normalize_key(value: str) -> str:
    normalized = value.replace("\\", "/").strip("/")
    while "//" in normalized:
        normalized = normalized.replace("//", "/")
    return normalized


def _is_remote_path(stored_path: str) -> bool:
    normalized = stored_path.replace("\\", "/")
    return (
        normalized.startswith("s3://")
        or normalized.startswith("r2://")
        or normalized.startswith("gdrive://")
    )


class PdfStorage:
    """
    Compatibility layer for Vera.Fidei PDFs.

    Default mode is local, preserving the existing /app/pdfs behavior. When
    PDF_STORAGE is "s3" or "r2", new uploads are copied to an S3-compatible
    bucket and the backend keeps only a bounded processing cache.
    """

    def __init__(self) -> None:
        self.backend = os.environ.get("PDF_STORAGE", "local").strip().lower() or "local"
        if self.backend == "r2":
            self.backend = "s3"
        if self.backend in {"drive", "google_drive", "google-drive"}:
            self.backend = "gdrive"
        self.bucket = os.environ.get("S3_BUCKET", "").strip()
        self.endpoint_url = os.environ.get("S3_ENDPOINT_URL", "").strip() or None
        self.region = os.environ.get("S3_REGION", "auto").strip() or "auto"
        self.prefix = _normalize_key(os.environ.get("S3_PREFIX", "pdfs"))
        self.public_base_url = os.environ.get("S3_PUBLIC_BASE_URL", "").strip().rstrip("/")
        self.presign_expires = int(os.environ.get("S3_PRESIGN_EXPIRES", "3600"))
        self.cache_max_gb = float(os.environ.get("PDF_CACHE_MAX_GB", "5"))
        self.gdrive_remote = os.environ.get("GDRIVE_REMOTE", "vera_drive").strip() or "vera_drive"
        self.gdrive_prefix = _normalize_key(os.environ.get("GDRIVE_PREFIX", self.prefix))
        self.rclone_bin = os.environ.get("RCLONE_BIN", "rclone").strip() or "rclone"
        self.rclone_timeout = int(os.environ.get("VERA_RCLONE_TIMEOUT", "600"))

        PDF_DIR.mkdir(parents=True, exist_ok=True)
        PDF_CACHE_DIR.mkdir(parents=True, exist_ok=True)

        self._s3_client = None
        if self.backend == "s3" and not self.bucket:
            raise RuntimeError("PDF_STORAGE=s3 requires S3_BUCKET.")

    @property
    def is_remote(self) -> bool:
        return self.backend in {"s3", "gdrive"}

    def save_pdf(self, book_id: int, original_filename: str, pdf_bytes: bytes) -> StoredPdf:
        timestamp = int(time.time())
        safe_name = _sanitize_filename(original_filename)
        stored_filename = f"{book_id}_{timestamp}_{safe_name}"

        if not self.is_remote:
            local_path = PDF_DIR / stored_filename
            local_path.write_bytes(pdf_bytes)
            return StoredPdf(
                stored_path=str(local_path),
                local_path=str(local_path),
                storage_backend="local",
            )

        if self.backend == "gdrive":
            key = _normalize_key(f"{self.gdrive_prefix}/uploads/{book_id}/{stored_filename}")
            cache_path = self._cache_path_for_key(key)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(pdf_bytes)
            self._rclone_copyto(str(cache_path), key)
            self._prune_cache()
            return StoredPdf(stored_path=f"gdrive://{key}", local_path=str(cache_path), storage_backend="gdrive")

        key = _normalize_key(f"{self.prefix}/uploads/{book_id}/{stored_filename}")
        cache_path = self._cache_path_for_key(key)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(pdf_bytes)

        self._client().put_object(
            Bucket=self.bucket,
            Key=key,
            Body=pdf_bytes,
            ContentType="application/pdf",
            ContentDisposition=_content_disposition(original_filename),
        )
        self._prune_cache()
        return StoredPdf(stored_path=f"s3://{self.bucket}/{key}", local_path=str(cache_path), storage_backend="s3")

    def upload_existing_pdf(
        self,
        book_id: int,
        file_id: int,
        original_filename: str,
        local_path: str,
    ) -> StoredPdf:
        path = Path(local_path)
        if not path.is_file():
            raise FileNotFoundError(local_path)

        if not self.is_remote:
            return StoredPdf(stored_path=str(path), local_path=str(path), storage_backend="local")

        safe_name = _sanitize_filename(original_filename or path.name)
        if self.backend == "gdrive":
            key = _normalize_key(f"{self.gdrive_prefix}/library/{book_id}/{file_id}_{safe_name}")
            self._rclone_copyto(str(path), key)
            cache_path = self._cache_path_for_key(key)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            if path.resolve() != cache_path.resolve():
                shutil.copy2(path, cache_path)
            self._prune_cache()
            return StoredPdf(stored_path=f"gdrive://{key}", local_path=str(cache_path), storage_backend="gdrive")

        key = _normalize_key(f"{self.prefix}/library/{book_id}/{file_id}_{safe_name}")
        self._client().upload_file(
            str(path),
            self.bucket,
            key,
            ExtraArgs={
                "ContentType": "application/pdf",
                "ContentDisposition": _content_disposition(original_filename or path.name),
            },
        )

        cache_path = self._cache_path_for_key(key)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        if path.resolve() != cache_path.resolve():
            shutil.copy2(path, cache_path)
        self._prune_cache()
        return StoredPdf(stored_path=f"s3://{self.bucket}/{key}", local_path=str(cache_path), storage_backend="s3")

    def delete_pdf(self, stored_path: str) -> None:
        if not stored_path:
            return
        if _is_remote_path(stored_path):
            if stored_path.replace("\\", "/").startswith("gdrive://"):
                _bucket, key = self._parse_remote_path(stored_path)
                if self.backend == "gdrive" and key:
                    try:
                        self._run_rclone("deletefile", self._gdrive_target(key))
                    except Exception:
                        pass
                try:
                    self._cache_path_for_key(key or stored_path).unlink(missing_ok=True)
                except OSError:
                    pass
                return

            bucket, key = self._parse_remote_path(stored_path)
            if self.is_remote and bucket and key:
                try:
                    self._client().delete_object(Bucket=bucket, Key=key)
                except Exception:
                    pass
            try:
                self._cache_path_for_key(key or stored_path).unlink(missing_ok=True)
            except OSError:
                pass
            return

        resolved = self.resolve_local_path(stored_path)
        if resolved:
            try:
                Path(resolved).unlink(missing_ok=True)
            except OSError:
                pass

    def resolve_local_path(self, stored_path: str) -> str | None:
        if not stored_path or _is_remote_path(stored_path):
            return None

        normalized = stored_path.replace("\\", "/")
        basename = normalized.split("/")[-1]
        if not basename:
            return None

        candidates: list[Path] = []
        path_obj = Path(stored_path)
        if path_obj.is_absolute():
            candidates.append(path_obj)
        else:
            candidates.append(PDF_DIR / normalized)
        candidates.append(PDF_DIR / basename)

        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)

        try:
            for fname in sorted(PDF_DIR.iterdir()):
                if fname.is_file() and fname.name.endswith(basename):
                    return str(fname)
        except OSError:
            pass

        try:
            for path in PDF_DIR.rglob(basename):
                if path.is_file():
                    return str(path)
        except OSError:
            pass

        return None

    def resolve_for_processing(self, stored_path: str) -> str | None:
        local = self.resolve_local_path(stored_path)
        if local:
            return local

        if not _is_remote_path(stored_path):
            return None

        if stored_path.replace("\\", "/").startswith("gdrive://"):
            _bucket, key = self._parse_remote_path(stored_path)
            if not key or self.backend != "gdrive":
                return None
            local_mirror = self._local_mirror_for_gdrive(stored_path)
            if local_mirror:
                return local_mirror
            cache_path = self._cache_path_for_key(key)
            if cache_path.is_file():
                try:
                    cache_path.touch()
                except OSError:
                    pass
                return str(cache_path)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._run_rclone("copyto", self._gdrive_target(key), str(cache_path))
            self._prune_cache()
            return str(cache_path)

        bucket, key = self._parse_remote_path(stored_path)
        if not bucket or not key:
            return None
        cache_path = self._cache_path_for_key(key)
        if cache_path.is_file():
            try:
                cache_path.touch()
            except OSError:
                pass
            return str(cache_path)

        if not self.is_remote:
            return None

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._client().download_file(bucket, key, str(cache_path))
        self._prune_cache()
        return str(cache_path)

    def response_for_pdf(
        self,
        stored_path: str,
        original_filename: str,
        range_header: str | None = None,
    ) -> Response:
        local = self.resolve_local_path(stored_path)
        if local:
            response = self._x_accel_response(local, original_filename)
            if response:
                return response

        if stored_path.replace("\\", "/").startswith("gdrive://"):
            local = self._local_mirror_for_gdrive(stored_path, original_filename)
            if local:
                response = self._x_accel_response(local, original_filename)
                if response:
                    return response

            local = self.resolve_for_processing(stored_path)
            if not local:
                raise HTTPException(status_code=404, detail="PDF remoto nao encontrado.")
            return self._file_response(local, original_filename, range_header)

        if _is_remote_path(stored_path):
            bucket, key = self._parse_remote_path(stored_path)
            if not bucket or not key:
                raise HTTPException(status_code=404, detail="PDF remoto invalido.")
            url = self._public_or_presigned_url(bucket, key, original_filename)
            return RedirectResponse(url=url, status_code=302)

        raise HTTPException(status_code=404, detail="PDF nao encontrado.")

    def _x_accel_response(self, local_path: str, original_filename: str) -> Response | None:
        filename = self._filename_for_x_accel(local_path)
        if not filename:
            return None
        response = Response()
        response.headers["X-Accel-Redirect"] = f"/protected_pdfs/{quote(filename, safe='/')}"
        response.headers["Content-Type"] = "application/pdf"
        response.headers["Content-Disposition"] = _content_disposition(original_filename)
        response.headers["Accept-Ranges"] = "bytes"
        return response

    def _local_mirror_for_gdrive(
        self,
        stored_path: str,
        original_filename: str | None = None,
    ) -> str | None:
        _bucket, key = self._parse_remote_path(stored_path)
        if not key:
            return None

        candidates: list[Path] = []
        prefix = f"{self.gdrive_prefix}/"
        if key.startswith(prefix):
            rel = key[len(prefix):]
            if rel:
                candidates.append(PDF_DIR / rel)

        if original_filename:
            candidates.append(PDF_DIR / original_filename)

        for candidate in candidates:
            try:
                if candidate.is_file():
                    return str(candidate)
            except OSError:
                pass
        return self._find_local_mirror_by_name(key)

    def _find_local_mirror_by_name(self, key: str) -> str | None:
        target_name = Path(key).name
        if not target_name:
            return None

        def comparable(name: str) -> str:
            safe = _sanitize_filename(name).lower()
            safe = re.sub(r"^\d+_", "", safe)
            safe = re.sub(r"^\d+_", "", safe)
            return safe

        target = comparable(target_name)
        if not target:
            return None

        try:
            for path in PDF_DIR.rglob("*.pdf"):
                if not path.is_file():
                    continue
                candidate = comparable(path.name)
                if candidate == target:
                    return str(path)
                if target in candidate or candidate in target:
                    return str(path)
        except OSError:
            return None
        return None

    def _file_response(
        self,
        local_path: str,
        original_filename: str,
        range_header: str | None,
    ) -> Response:
        path = Path(local_path)
        if not path.is_file():
            raise HTTPException(status_code=404, detail="PDF nao encontrado.")

        headers = {
            "Content-Disposition": _content_disposition(original_filename),
            "Accept-Ranges": "bytes",
        }
        file_size = path.stat().st_size
        parsed_range = self._parse_range_header(range_header, file_size)
        if parsed_range is None:
            return FileResponse(local_path, media_type="application/pdf", headers=headers)

        start, end = parsed_range
        content_length = end - start + 1
        headers.update(
            {
                "Content-Length": str(content_length),
                "Content-Range": f"bytes {start}-{end}/{file_size}",
            }
        )
        return StreamingResponse(
            self._iter_file_range(path, start, end),
            status_code=206,
            media_type="application/pdf",
            headers=headers,
        )

    def _parse_range_header(self, range_header: str | None, file_size: int) -> tuple[int, int] | None:
        if not range_header:
            return None
        match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip())
        if not match:
            return None

        start_raw, end_raw = match.groups()
        if not start_raw and not end_raw:
            return None

        if start_raw:
            start = int(start_raw)
            end = int(end_raw) if end_raw else file_size - 1
        else:
            suffix_length = int(end_raw)
            if suffix_length <= 0:
                return None
            start = max(file_size - suffix_length, 0)
            end = file_size - 1

        if start >= file_size or end < start:
            raise HTTPException(
                status_code=416,
                detail="Intervalo de bytes invalido.",
                headers={"Content-Range": f"bytes */{file_size}"},
            )
        return start, min(end, file_size - 1)

    def _iter_file_range(self, path: Path, start: int, end: int):
        chunk_size = 1024 * 1024
        remaining = end - start + 1
        with path.open("rb") as handle:
            handle.seek(start)
            while remaining > 0:
                data = handle.read(min(chunk_size, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data

    def _filename_for_x_accel(self, local_path: str) -> str | None:
        path = Path(local_path)
        try:
            rel = path.resolve().relative_to(PDF_DIR)
            return rel.as_posix()
        except ValueError:
            if path.name and (PDF_DIR / path.name).is_file():
                return path.name
        return None

    def _public_or_presigned_url(self, bucket: str, key: str, original_filename: str) -> str:
        if self.public_base_url:
            return f"{self.public_base_url}/{quote(key, safe='/')}"
        if not self.is_remote:
            raise HTTPException(status_code=404, detail="Storage remoto nao configurado.")
        params = {
            "Bucket": bucket,
            "Key": key,
            "ResponseContentType": "application/pdf",
            "ResponseContentDisposition": _content_disposition(original_filename),
        }
        return self._client().generate_presigned_url(
            "get_object",
            Params=params,
            ExpiresIn=self.presign_expires,
        )

    def _parse_remote_path(self, stored_path: str) -> tuple[str | None, str | None]:
        normalized = stored_path.replace("\\", "/")
        if normalized.startswith("gdrive://"):
            _scheme, rest = normalized.split("://", 1)
            return None, _normalize_key(rest)
        if normalized.startswith("s3://") or normalized.startswith("r2://"):
            _, rest = normalized.split("://", 1)
            bucket, _, key = rest.partition("/")
            return bucket or self.bucket, _normalize_key(key)
        if self.is_remote:
            return self.bucket, _normalize_key(normalized)
        return None, None

    def _cache_path_for_key(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
        name = f"{digest}_{_sanitize_filename(Path(key).name)}"
        return PDF_CACHE_DIR / name

    def _prune_cache(self) -> None:
        if self.cache_max_gb <= 0:
            return
        max_bytes = int(self.cache_max_gb * 1024 * 1024 * 1024)
        files = [p for p in PDF_CACHE_DIR.glob("*") if p.is_file()]
        total = sum(p.stat().st_size for p in files)
        if total <= max_bytes:
            return
        files.sort(key=lambda p: p.stat().st_atime)
        for path in files:
            if total <= max_bytes:
                break
            try:
                size = path.stat().st_size
                path.unlink()
                total -= size
            except OSError:
                pass

    def _client(self):
        if self._s3_client is None:
            try:
                import boto3
            except ImportError as exc:
                raise RuntimeError("PDF_STORAGE=s3 requires boto3 installed.") from exc

            kwargs = {
                "service_name": "s3",
                "region_name": self.region,
            }
            if self.endpoint_url:
                kwargs["endpoint_url"] = self.endpoint_url
            access_key = os.environ.get("S3_ACCESS_KEY_ID") or os.environ.get("AWS_ACCESS_KEY_ID")
            secret_key = os.environ.get("S3_SECRET_ACCESS_KEY") or os.environ.get("AWS_SECRET_ACCESS_KEY")
            if access_key and secret_key:
                kwargs["aws_access_key_id"] = access_key
                kwargs["aws_secret_access_key"] = secret_key
            self._s3_client = boto3.client(**kwargs)
        return self._s3_client

    def remote_size(self, stored_path: str) -> int | None:
        normalized = (stored_path or "").replace("\\", "/")
        if normalized.startswith("gdrive://"):
            _bucket, key = self._parse_remote_path(stored_path)
            if not key:
                return None
            result = self._run_rclone("size", "--json", self._gdrive_target(key))
            payload = json.loads(result.stdout or "{}")
            return int(payload.get("bytes") or 0)

        bucket, key = self._parse_remote_path(stored_path)
        if bucket and key:
            response = self._client().head_object(Bucket=bucket, Key=key)
            return int(response.get("ContentLength") or 0)
        return None

    def check_remote_write(self) -> None:
        body = b"vera-fidei-remote-preflight\n"
        if self.backend == "gdrive":
            key = _normalize_key(f"{self.gdrive_prefix}/_migration_preflight.txt")
            cache_path = PDF_CACHE_DIR / "_migration_preflight.txt"
            cache_path.write_bytes(body)
            self._rclone_copyto(str(cache_path), key)
            size = self.remote_size(f"gdrive://{key}")
            if size != len(body):
                raise RuntimeError(f"preflight object size mismatch: {size} != {len(body)}")
            self._run_rclone("deletefile", self._gdrive_target(key))
            cache_path.unlink(missing_ok=True)
            return

        key = f"{self.prefix}/_migration_preflight.txt"
        self._client().put_object(
            Bucket=self.bucket,
            Key=key,
            Body=body,
            ContentType="text/plain",
        )
        response = self._client().head_object(Bucket=self.bucket, Key=key)
        size = int(response.get("ContentLength") or 0)
        if size != len(body):
            raise RuntimeError(f"preflight object size mismatch: {size} != {len(body)}")
        self._client().delete_object(Bucket=self.bucket, Key=key)

    def _gdrive_target(self, key: str) -> str:
        return f"{self.gdrive_remote}:{_normalize_key(key)}"

    def _rclone_copyto(self, local_path: str, key: str) -> None:
        self._run_rclone("copyto", local_path, self._gdrive_target(key))

    def _run_rclone(self, *args: str) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(
                [self.rclone_bin, *args],
                check=True,
                capture_output=True,
                text=True,
                timeout=self.rclone_timeout,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("PDF_STORAGE=gdrive requires rclone installed.") from exc
        except subprocess.CalledProcessError as exc:
            details = (exc.stderr or exc.stdout or "").strip()
            raise RuntimeError(f"rclone failed: {' '.join(args)}\n{details}") from exc


_storage: PdfStorage | None = None


def get_pdf_storage() -> PdfStorage:
    global _storage
    if _storage is None:
        _storage = PdfStorage()
    return _storage
