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


def _iter_shards(output_dir: Path):
    yield from sorted(output_dir.glob("embeddings_*.jsonl.gz"))


def _read_completed_ids(output_dir: Path) -> set[int]:
    completed: set[int] = set()
    for path in _iter_shards(output_dir):
        try:
            with gzip.open(path, "rt", encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        completed.add(int(json.loads(line)["chunk_id"]))
        except Exception:
            print(f"ignoring_corrupt_shard={path}", flush=True)
    return completed


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


def _write_shard(output_dir: Path, shard_index: int, batch: list[dict], embeddings: list[list[float]]) -> Path:
    final = output_dir / f"embeddings_{shard_index:05d}.jsonl.gz"
    tmp = output_dir / f"embeddings_{shard_index:05d}.jsonl.gz.tmp"
    with gzip.open(tmp, "wt", encoding="utf-8") as fh:
        for item, embedding in zip(batch, embeddings):
            payload = {
                "chunk_id": item["chunk_id"],
                "text": item["text"],
                "language": item.get("language") or "unknown",
                "metadata": item.get("metadata") or {},
                "embedding": embedding,
            }
            fh.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    tmp.replace(final)
    return final


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--model", default=settings.embedding_model)
    parser.add_argument("--device", default=os.environ.get("VERA_EMBEDDING_DEVICE", "cuda"))
    parser.add_argument("--items-per-shard", type=int, default=32)
    parser.add_argument("--encode-batch-size", type=int, default=1)
    parser.add_argument("--max-shards", type=int, default=0)
    parser.add_argument("--max-items", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument("--max-gpu-power-watts", type=float, default=0.0)
    parser.add_argument("--max-gpu-temp-c", type=int, default=0)
    parser.add_argument("--cooldown-seconds", type=float, default=10.0)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for tmp in output_dir.glob("*.tmp"):
        try:
            tmp.unlink()
        except Exception:
            pass

    completed_ids = _read_completed_ids(output_dir) if args.resume else set()
    next_shard = len(list(_iter_shards(output_dir)))
    print(f"completed_ids={len(completed_ids)} next_shard={next_shard}", flush=True)

    model = SentenceTransformer(args.model, device=args.device)
    batch: list[dict] = []
    embedded = 0
    skipped = 0
    shards = 0

    def flush_batch() -> None:
        nonlocal batch, embedded, shards, next_shard
        if not batch:
            return
        _cooldown_if_needed(args.max_gpu_power_watts, args.max_gpu_temp_c, args.cooldown_seconds)
        embeddings = model.encode(
            [entry["text"] for entry in batch],
            batch_size=max(1, min(args.encode_batch_size, len(batch))),
            show_progress_bar=False,
        ).tolist()
        path = _write_shard(output_dir, next_shard, batch, embeddings)
        embedded += len(batch)
        shards += 1
        next_shard += 1
        power, temp = _gpu_stats()
        print(f"shard={path.name} embedded={embedded} skipped={skipped} power={power}W temp={temp}C", flush=True)
        batch = []
        if args.sleep_seconds > 0:
            time.sleep(args.sleep_seconds)

    for item in _read_jobs(Path(args.input)):
        chunk_id = int(item["chunk_id"])
        if chunk_id in completed_ids:
            skipped += 1
            continue
        batch.append(item)
        if len(batch) >= args.items_per_shard:
            flush_batch()
            if args.max_shards and shards >= args.max_shards:
                break
            if args.max_items and embedded >= args.max_items:
                break

    if batch and not (args.max_shards and shards >= args.max_shards) and not (args.max_items and embedded >= args.max_items):
        flush_batch()

    print(f"embedded_total={embedded} skipped={skipped} shards={shards} output_dir={output_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
