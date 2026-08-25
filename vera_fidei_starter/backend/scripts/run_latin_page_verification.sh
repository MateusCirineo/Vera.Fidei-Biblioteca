#!/bin/sh
set -u

cd /opt/vera_fidei || exit 1

log_dir=/opt/vera_fidei/backend/pdfs/.page_verification
log_file="$log_dir/latin-page-verification.log"
cid_file="$log_dir/latin-page-verification.cid"
ocr_cpus="${VERA_PAGE_VERIFY_CPUS:-3.0}"
ocr_workers="${VERA_PAGE_VERIFY_WORKERS:-3}"
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

while systemctl is-active --quiet vera-latin-reindex.service \
  || systemctl is-active --quiet vera-greek-latin-reindex.service \
  || systemctl is-active --quiet vera-orientalis-latin-reindex.service; do
  printf '%s waiting_for_candidate_ocr\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$log_file"
  sleep 60
done

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
    --memory 5g \
    --memory-swap 5g \
    --env-file /opt/vera_fidei/backend/.env.production \
    -e PDF_STORAGE="$storage_backend" \
    -e GDRIVE_PREFIX="$gdrive_prefix" \
    -e GDRIVE_REMOTE="$gdrive_remote" \
    -e RCLONE_CONFIG=/app/rclone/rclone.conf \
    -e VERA_ENABLE_SEMANTIC_SEARCH=false \
    -e TESSDATA_DIR=/app/pdfs/.verification_tessdata \
    -e OMP_THREAD_LIMIT=1 \
    -e OMP_NUM_THREADS=1 \
    -v /opt/vera_fidei/backend/pdfs:/app/pdfs \
    -v /opt/vera_fidei/backend/rclone:/app/rclone \
    -v /opt/vera_fidei/backend/scripts:/app/scripts:ro \
    -v /opt/vera_fidei/backend/services/page_verification_service.py:/app/services/page_verification_service.py:ro \
    "$backend_image" \
    python -m scripts.build_page_verification_queue \
      --workers "$ocr_workers" "$@" >> "$log_file" 2>&1
  status=$?
  rm -f "$cid_file"
  printf '%s group_done %s status=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$label" "$status" >> "$log_file"
  return "$status"
}

failed=0

run_group patrologia_latina \
  --book-id 1742 --book-id 1743 --book-id 1776 --book-id 1778 \
  --book-id 2144 --book-id 2145 --book-id 2146 \
  --candidate-source ocr_cache --candidate-lang lat+grc+eng \
  --verifier-lang Latin+lat+grc+eng --layout columns || failed=1

run_group patrologia_graeca_bilingual \
  --book-id 32 --book-id 1739 --book-id 1779 --book-id 1740 --book-id 1741 \
  --candidate-source ocr_cache --candidate-lang lat+grc+eng \
  --verifier-lang Latin+lat+grc+eng --layout columns || failed=1

run_group patrologia_orientalis_multilingual \
  --book-id 2136 --book-id 2137 --book-id 2138 --book-id 2139 \
  --book-id 2140 --book-id 2141 --book-id 2142 --book-id 2143 \
  --candidate-source ocr_cache --candidate-lang lat+grc+fra+eng \
  --verifier-lang Latin+lat+grc+fra+eng --layout columns || failed=1

run_group summa_bilingual \
  --book-id 2109 --book-id 2110 --book-id 2111 --book-id 2112 \
  --candidate-source ocr_cache --candidate-lang lat+por \
  --verifier-lang Latin+lat+por --layout columns || failed=1

run_group mixed_scans \
  --book-id 1777 --book-id 2158 \
  --candidate-source ocr_cache --candidate-lang lat+grc+eng \
  --verifier-lang Latin+lat+grc+eng --layout auto || failed=1

run_group born_digital_latin \
  --book-id 1863 --book-id 1867 --book-id 1880 --book-id 1886 \
  --book-id 1892 --book-id 1898 --book-id 1904 --book-id 1910 \
  --book-id 1916 --book-id 1922 --book-id 1928 --book-id 1934 \
  --book-id 1940 --book-id 1946 --book-id 1952 --book-id 1958 \
  --book-id 1964 --book-id 1970 --book-id 2007 --book-id 2011 \
  --candidate-source pdf_text --candidate-lang lat+por+eng \
  --verifier-lang Latin+lat+por+eng --layout auto || failed=1

printf '%s verification_pipeline_done status=%s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$failed" >> "$log_file"
exit "$failed"
