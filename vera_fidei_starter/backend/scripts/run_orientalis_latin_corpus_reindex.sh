#!/bin/sh
set -u

cd /opt/vera_fidei || exit 1

log_dir=/opt/vera_fidei/backend/pdfs/.ocr_reindex_backups
log_file="$log_dir/orientalis-latin-corpus-reindex.log"
cid_file="$log_dir/orientalis-latin-corpus-reindex.cid"
ocr_cpus="${VERA_ORIENTALIS_OCR_CPUS:-1.0}"
ocr_workers="${VERA_ORIENTALIS_OCR_WORKERS:-1}"
mkdir -p "$log_dir"

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

# Do not increase production contention while PL and PG candidate OCR are live.
while systemctl is-active --quiet vera-latin-reindex.service \
  || systemctl is-active --quiet vera-greek-latin-reindex.service; do
  printf '%s waiting_for_pl_pg_ocr\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$log_file"
  sleep 60
done

printf '%s group_start patrologia_orientalis_latin\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$log_file"
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
  python -m scripts.ocr_reindex_books \
    --book-id 2136 --book-id 2137 --book-id 2138 --book-id 2139 \
    --book-id 2140 --book-id 2141 --book-id 2142 --book-id 2143 \
    --layout columns --lang lat+grc+fra+eng --workers "$ocr_workers" >> "$log_file" 2>&1
status=$?
rm -f "$cid_file"
printf '%s group_done patrologia_orientalis_latin status=%s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$status" >> "$log_file"
exit "$status"
