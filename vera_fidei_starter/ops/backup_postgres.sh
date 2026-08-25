#!/bin/sh
set -eu

project_dir="${VERA_PROJECT_DIR:-/opt/vera_fidei}"
backup_dir="${VERA_BACKUP_DIR:-/var/backups/vera-fidei/postgres}"
retention_days="${VERA_BACKUP_RETENTION_DAYS:-14}"
database="${POSTGRES_DB:-vera_fidei}"
database_user="${POSTGRES_USER:-vera}"

case "$backup_dir" in
    /var/backups/vera-fidei/postgres|/var/backups/vera-fidei/postgres/*) ;;
    *)
        echo "Refusing unsafe backup directory: $backup_dir" >&2
        exit 2
        ;;
esac

case "$retention_days" in
    ''|*[!0-9]*)
        echo "VERA_BACKUP_RETENTION_DAYS must be a positive integer" >&2
        exit 2
        ;;
esac

umask 077
mkdir -p "$backup_dir"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
archive="$backup_dir/vera-fidei-$stamp.dump"
temporary="$backup_dir/.vera-fidei-$stamp.dump.tmp"

cleanup() {
    rm -f -- "$temporary"
}
trap cleanup EXIT HUP INT TERM

cd "$project_dir"
docker compose exec -T postgres \
    pg_dump --username "$database_user" --dbname "$database" \
    --format=custom --compress=6 --no-owner --no-acl </dev/null > "$temporary"

test -s "$temporary"
docker compose exec -T postgres pg_restore --list < "$temporary" >/dev/null
mv -- "$temporary" "$archive"
sha256sum "$archive" > "$archive.sha256"

# Only this application's timestamped archives are eligible for retention.
find "$backup_dir" -maxdepth 1 -type f \
    \( -name 'vera-fidei-*.dump' -o -name 'vera-fidei-*.dump.sha256' \) \
    -mtime "+$retention_days" -delete

echo "PostgreSQL backup created and catalog-validated: $archive"
