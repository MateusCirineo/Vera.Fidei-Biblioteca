#!/bin/sh
set -u

cd /opt/vera_fidei || exit 1

log_dir=/opt/vera_fidei/backend/pdfs/.ocr_reindex_backups
log_file="$log_dir/latin-corpus-reindex.log"
cid_file="$log_dir/latin-corpus-reindex.cid"
ocr_cpus="${VERA_LATIN_OCR_CPUS:-2.0}"
ocr_workers="${VERA_LATIN_OCR_WORKERS:-2}"
mkdir -p "$log_dir"

# Compose supplies storage routing overrides in addition to the env file. Read
# only these non-secret values from the healthy backend so isolated jobs resolve
# the exact stored_path instead of an unrelated same-name local PDF.
storage_backend="$(docker exec vera_fidei-backend-1 python -c 'from storage.pdf_storage import get_pdf_storage; print(get_pdf_storage().backend)')"
gdrive_prefix="$(docker exec vera_fidei-backend-1 python -c 'from storage.pdf_storage import get_pdf_storage; print(get_pdf_storage().gdrive_prefix)')"
gdrive_remote="$(docker exec vera_fidei-backend-1 python -c 'from storage.pdf_storage import get_pdf_storage; print(get_pdf_storage().gdrive_remote)')"

cleanup() {
  if [ -s "$cid_file" ]; then
    container_id="$(cat "$cid_file")"
    docker stop -t 20 "$container_id" >/dev/null 2>&1 || true
    rm -f "$cid_file"
  fi
}

trap cleanup INT TERM EXIT

run_group() {
  label="$1"
  shift
  printf '%s group_start %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$label" >> "$log_file"
  rm -f "$cid_file"
  backend_image="$(docker inspect vera_fidei-backend-1 --format '{{.Config.Image}}')"
  docker run --rm \
    --cidfile "$cid_file" \
    --network vera_fidei_default \
    --cpus "$ocr_cpus" \
    --memory 3g \
    --memory-swap 3g \
    --env-file /opt/vera_fidei/backend/.env.production \
    -e PDF_STORAGE="$storage_backend" \
    -e GDRIVE_PREFIX="$gdrive_prefix" \
    -e GDRIVE_REMOTE="$gdrive_remote" \
    -e RCLONE_CONFIG=/app/rclone/rclone.conf \
    -e VERA_ENABLE_SEMANTIC_SEARCH=false \
    -e OMP_THREAD_LIMIT=1 \
    -e OMP_NUM_THREADS=1 \
    -v /opt/vera_fidei/backend/chroma_db:/app/chroma_db \
    -v /opt/vera_fidei/backend/pdfs:/app/pdfs \
    -v /opt/vera_fidei/backend/rclone:/app/rclone \
    -v /opt/vera_fidei/backend/scripts:/app/scripts:ro \
    "$backend_image" \
    python -m scripts.ocr_reindex_books "$@" >> "$log_file" 2>&1
  status=$?
  rm -f "$cid_file"
  printf '%s group_done %s status=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$label" "$status" >> "$log_file"
  return "$status"
}

failed=0
selected_groups="${VERA_LATIN_GROUPS:-all}"

group_enabled() {
  [ "$selected_groups" = "all" ] && return 0
  case ",$selected_groups," in
    *",$1,"*) return 0 ;;
    *) return 1 ;;
  esac
}

# Migne volumes whose body is visibly set in two independent columns.
if group_enabled patrologia_columns; then
  run_group patrologia_columns \
    --book-id 1742 --book-id 1743 --book-id 1776 --book-id 1778 \
    --book-id 2144 --book-id 2145 --book-id 2146 \
    --layout columns --lang lat+grc+eng --workers "$ocr_workers" || failed=1
fi

# Bilingual Latin/Portuguese facing columns.
if group_enabled summa_bilingual; then
  run_group summa_bilingual \
    --book-id 2109 --book-id 2110 --book-id 2111 --book-id 2112 \
    --layout columns --lang lat+por --workers "$ocr_workers" || failed=1
fi

# Single-column or mixed body/footnote layouts use automatic segmentation.
if group_enabled mixed_layout; then
  run_group mixed_layout \
    --book-id 1777 --book-id 2158 \
    --layout auto --lang lat+grc+eng --workers "$ocr_workers" || failed=1
fi

printf '%s latin_candidate_pipeline_done status=%s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$failed" >> "$log_file"
exit "$failed"
