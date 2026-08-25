#!/bin/sh
set -eu

project_dir="${VERA_PROJECT_DIR:-/opt/vera_fidei}"
backup_dir="${VERA_BACKUP_DIR:-/var/backups/vera-fidei/postgres}"
database_user="${POSTGRES_USER:-vera}"
archive="${1:-}"

case "$backup_dir" in
    /var/backups/vera-fidei/postgres|/var/backups/vera-fidei/postgres/*) ;;
    *)
        echo "Refusing unsafe backup directory: $backup_dir" >&2
        exit 2
        ;;
esac

if [ -z "$archive" ]; then
    archive="$(find "$backup_dir" -maxdepth 1 -type f -name 'vera-fidei-*.dump' \
        -printf '%T@ %p\n' | sort -n | tail -n 1 | cut -d ' ' -f 2-)"
fi
if [ -z "$archive" ] || [ ! -f "$archive" ]; then
    echo "No PostgreSQL backup archive found" >&2
    exit 2
fi

checksum_file="${archive}.sha256"
if [ ! -f "$checksum_file" ] || ! (
    cd "$(dirname "$archive")"
    sha256sum --check --status "$(basename "$checksum_file")"
); then
    echo "Backup checksum is missing or invalid: $archive" >&2
    exit 2
fi

restore_db="vera_fidei_restore_$(date -u +%Y%m%d%H%M%S)_$$"
case "$restore_db" in
    vera_fidei_restore_[0-9]*) ;;
    *) exit 2 ;;
esac

cd "$project_dir"
drop_restore_db() {
    docker compose exec -T postgres \
        dropdb --username "$database_user" --if-exists --force "$restore_db" >/dev/null 2>&1 || true
}
trap drop_restore_db EXIT HUP INT TERM

docker compose exec -T postgres createdb --username "$database_user" "$restore_db"
docker compose exec -T postgres \
    pg_restore --username "$database_user" --dbname "$restore_db" \
    --no-owner --no-acl --exit-on-error < "$archive"

counts="$(docker compose exec -T postgres psql --username "$database_user" --dbname "$restore_db" \
    --tuples-only --no-align --command \
    "SELECT 'books=' || count(*) FROM books UNION ALL SELECT 'chunks=' || count(*) FROM chunks UNION ALL SELECT 'users=' || count(*) FROM users;")"

printf '%s\n' "$counts"
echo "Restore test completed successfully from: $archive"
