from __future__ import annotations

import argparse
import gzip
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

from sentence_transformers import SentenceTransformer

from core.config import settings


def _read_jobs(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def _write_batch(out_fh, batch: list[dict], embeddings: list[list[float]]) -> int:
    for item, embedding in zip(batch, embeddings):
        payload = {
            "chunk_id": item["chunk_id"],
            "text": item["text"],
            "language": item.get("language") or "unknown",
            "metadata": item.get("metadata") or {},
            "embedding": embedding,
        }
        out_fh.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    return len(batch)


def _read_existing_chunk_ids(path: Path) -> set[int]:
    if not path.exists() or path.stat().st_size == 0:
        return set()
    ids: set[int] = set()
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
                ids.add(int(item["chunk_id"]))
            except Exception:
                continue
    return ids


def _gpu_stats() -> tuple[float | None, int | None]:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=power.draw,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None, None
        first = (result.stdout or "").strip().splitlines()[0]
        power_raw, temp_raw = [part.strip() for part in first.split(",", 1)]
        return float(power_raw), int(float(temp_raw))
    except Exception:
        return None, None


def _cooldown_if_needed(max_power_watts: float, max_temp_c: int, cooldown_seconds: float) -> None:
    if max_power_watts <= 0 and max_temp_c <= 0:
        return
    while True:
        power, temp = _gpu_stats()
        too_hot = temp is not None and max_temp_c > 0 and temp >= max_temp_c
        too_powerful = power is not None and max_power_watts > 0 and power >= max_power_watts
        if not (too_hot or too_powerful):
            return
        print(f"cooldown power={power}W temp={temp}C", flush=True)
        time.sleep(max(1.0, cooldown_seconds))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", default=settings.embedding_model)
    parser.add_argument("--device", default=os.environ.get("VERA_EMBEDDING_DEVICE", "cuda"))
    parser.add_argument("--batch-size", type=int, default=int(os.environ.get("VERA_SEMANTIC_INDEX_BATCH_SIZE", "16")))
    parser.add_argument("--max-items", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument("--max-gpu-power-watts", type=float, default=0.0)
    parser.add_argument("--max-gpu-temp-c", type=int, default=0)
    parser.add_argument("--cooldown-seconds", type=float, default=10.0)
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    existing_ids = _read_existing_chunk_ids(output_path) if args.resume else set()
    output_mode = "at" if args.resume and output_path.exists() else "wt"

    model = SentenceTransformer(args.model, device=args.device)
    processed = 0
    skipped = 0
    batch: list[dict] = []

    with gzip.open(output_path, output_mode, encoding="utf-8") as out_fh:
        for item in _read_jobs(input_path):
            if int(item["chunk_id"]) in existing_ids:
                skipped += 1
                continue
            batch.append(item)
            if len(batch) >= args.batch_size:
                _cooldown_if_needed(args.max_gpu_power_watts, args.max_gpu_temp_c, args.cooldown_seconds)
                embeddings = model.encode(
                    [entry["text"] for entry in batch],
                    batch_size=min(args.batch_size, len(batch)),
                    show_progress_bar=False,
                ).tolist()
                processed += _write_batch(out_fh, batch, embeddings)
                out_fh.flush()
                power, temp = _gpu_stats()
                print(f"embedded={processed} skipped={skipped} power={power}W temp={temp}C", flush=True)
                batch = []
                if args.sleep_seconds > 0:
                    time.sleep(args.sleep_seconds)
                if args.max_items and processed >= args.max_items:
                    break

        if batch and not (args.max_items and processed >= args.max_items):
            _cooldown_if_needed(args.max_gpu_power_watts, args.max_gpu_temp_c, args.cooldown_seconds)
            embeddings = model.encode(
                [entry["text"] for entry in batch],
                batch_size=min(args.batch_size, len(batch)),
                show_progress_bar=False,
            ).tolist()
            processed += _write_batch(out_fh, batch, embeddings)
            out_fh.flush()
            power, temp = _gpu_stats()
            print(f"embedded={processed} skipped={skipped} power={power}W temp={temp}C", flush=True)

    print(f"embedded_total={processed} skipped={skipped} output={output_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
