#!/usr/bin/env bash
set -Eeuo pipefail

backup_dir="${VERA_BACKUP_DIR:-/var/backups/vera-fidei/postgres}"
stage_dir="${VERA_OFFSITE_STAGE_DIR:-/var/backups/vera-fidei/offsite-stage}"
recipient_file="${VERA_BACKUP_RECIPIENT_FILE:-/etc/vera-fidei/backup-recipient.pub}"
remote_dir="${VERA_OFFSITE_REMOTE:-vera_drive:vera-fidei/backups/postgres-encrypted}"
success_marker="${VERA_OFFSITE_SUCCESS_MARKER:-/var/lib/vera-fidei/offsite-backup-success}"

case "$backup_dir" in
    /var/backups/vera-fidei/postgres|/var/backups/vera-fidei/postgres/*) ;;
    *) echo "Refusing unsafe backup directory: $backup_dir" >&2; exit 2 ;;
esac
case "$stage_dir" in
    /var/backups/vera-fidei/offsite-stage|/var/backups/vera-fidei/offsite-stage/*) ;;
    *) echo "Refusing unsafe staging directory: $stage_dir" >&2; exit 2 ;;
esac
case "$success_marker" in
    /var/lib/vera-fidei/offsite-backup-success) ;;
    *) echo "Refusing unsafe success marker: $success_marker" >&2; exit 2 ;;
esac

for command_name in age rclone sha256sum; do
    command -v "$command_name" >/dev/null 2>&1 || {
        echo "Required command is unavailable: $command_name" >&2
        exit 2
    }
done

if [[ ! -s "$recipient_file" ]] || ! grep -Eq '^ssh-(ed25519|rsa) ' "$recipient_file"; then
    echo "A valid SSH backup recipient is required: $recipient_file" >&2
    exit 2
fi

archive="$(find "$backup_dir" -maxdepth 1 -type f -name 'vera-fidei-*.dump' \
    -printf '%T@ %p\n' | sort -n | tail -n 1 | cut -d ' ' -f 2-)"
if [[ -z "$archive" || ! -f "$archive" ]]; then
    echo "No PostgreSQL backup archive found" >&2
    exit 2
fi

archive_checksum="${archive}.sha256"
if [[ ! -s "$archive_checksum" ]] || ! (
    cd "$backup_dir"
    sha256sum --check --status "$(basename "$archive_checksum")"
); then
    echo "Local PostgreSQL backup checksum is missing or invalid: $archive" >&2
    exit 2
fi

install -d -m 0700 "$stage_dir"
install -d -m 0700 "$(dirname "$success_marker")"
archive_name="$(basename "$archive")"
encrypted_name="${archive_name}.age"
encrypted_file="$stage_dir/$encrypted_name"
encrypted_checksum="$stage_dir/${encrypted_name}.sha256"
temporary_file="$stage_dir/.${encrypted_name}.tmp"
remote_copy="$stage_dir/.${encrypted_name}.remote-copy"
remote_checksum_copy="$stage_dir/.${encrypted_name}.remote-checksum"

cleanup() {
    rm -f -- \
        "$temporary_file" \
        "$encrypted_file" \
        "$encrypted_checksum" \
        "$remote_copy" \
        "$remote_checksum_copy"
}
trap cleanup EXIT HUP INT TERM

age --encrypt --recipients-file "$recipient_file" --output "$temporary_file" "$archive"
mv -- "$temporary_file" "$encrypted_file"
(
    cd "$stage_dir"
    sha256sum "$encrypted_name" > "${encrypted_name}.sha256"
)

rclone copyto "$encrypted_file" "$remote_dir/$encrypted_name" --retries 4 --low-level-retries 10
rclone copyto "$encrypted_checksum" "$remote_dir/${encrypted_name}.sha256" --retries 4 --low-level-retries 10
rclone check "$stage_dir" "$remote_dir" \
    --include "$encrypted_name" \
    --include "${encrypted_name}.sha256" \
    --one-way --size-only

# Rebaixa exatamente os dois objetos enviados e valida o conteúdo cifrado pelo
# SHA-256. Isso detecta corrupção remota mesmo quando o provedor não oferece um
# algoritmo de hash compatível ao `rclone check`.
rclone copyto "$remote_dir/$encrypted_name" "$remote_copy" \
    --retries 4 --low-level-retries 10
rclone copyto "$remote_dir/${encrypted_name}.sha256" "$remote_checksum_copy" \
    --retries 4 --low-level-retries 10
remote_expected_checksum="$(awk 'NF {print $1; exit}' "$remote_checksum_copy")"
remote_actual_checksum="$(sha256sum "$remote_copy" | awk '{print $1}')"
if [[ ! "$remote_expected_checksum" =~ ^[0-9a-fA-F]{64}$ ]] || \
        [[ "${remote_expected_checksum,,}" != "${remote_actual_checksum,,}" ]]; then
    echo "Remote encrypted backup checksum verification failed: $remote_dir/$encrypted_name" >&2
    exit 1
fi

printf '%s %s\n' "$(date --iso-8601=seconds)" "$encrypted_name" > "$success_marker"
chmod 0600 "$success_marker"
echo "Encrypted off-site PostgreSQL backup verified: $remote_dir/$encrypted_name"
