#!/usr/bin/env bash
set -Eeuo pipefail

project_dir="${VERA_PROJECT_DIR:-/opt/vera_fidei}"
backup_dir="${VERA_BACKUP_DIR:-/var/backups/vera-fidei/postgres}"
state_dir="${VERA_MONITOR_STATE_DIR:-/var/lib/vera-fidei-monitor}"
public_url="${VERA_PUBLIC_URL:-https://verafidei.com.br/apresentacao}"
legacy_public_url="${VERA_LEGACY_PUBLIC_URL-https://verafidei.oialfred.com/apresentacao}"
disk_limit="${VERA_DISK_LIMIT_PERCENT:-80}"
backup_max_age_hours="${VERA_BACKUP_MAX_AGE_HOURS:-36}"
offsite_marker="${VERA_OFFSITE_SUCCESS_MARKER:-/var/lib/vera-fidei/offsite-backup-success}"
offsite_max_age_hours="${VERA_OFFSITE_MAX_AGE_HOURS:-36}"
billing_reconcile_unit="${VERA_BILLING_RECONCILE_UNIT:-vera-fidei-billing-reconcile.service}"

case "$state_dir" in
    /var/lib/vera-fidei-monitor|/var/lib/vera-fidei-monitor/*) ;;
    *)
        echo "Refusing unsafe monitor state directory: $state_dir" >&2
        exit 2
        ;;
esac

case "$disk_limit:$backup_max_age_hours:$offsite_max_age_hours" in
    *[!0-9:]*|:*|*:|*::*)
        echo "Monitor thresholds must be positive integers" >&2
        exit 2
        ;;
esac

mkdir -p "$state_dir"
status_file="$state_dir/status"
previous_status="$(cat "$status_file" 2>/dev/null || printf 'unknown')"
failures=()
curl_health_args=(
    --fail
    --silent
    --show-error
    --location
    --connect-timeout 10
    --max-time 25
    --retry 3
    --retry-all-errors
    --retry-delay 2
    --retry-max-time 45
    --output /dev/null
)

fail() {
    failures+=("$1")
}

send_email() {
    local subject="$1"
    local message="$2"
    (
        cd "$project_dir"
        docker compose exec -T \
            -e VERA_MONITOR_SUBJECT="$subject" \
            -e VERA_MONITOR_MESSAGE="$message" \
            backend python -c \
            'import html, os; from core.config import settings; from core.email import send_email; subject=os.environ["VERA_MONITOR_SUBJECT"]; message=os.environ["VERA_MONITOR_MESSAGE"]; send_email(settings.support_email, subject, "<p>" + html.escape(message) + "</p>")'
    ) || echo "Monitor could not send the notification email" >&2
}

if ! curl "${curl_health_args[@]}" "$public_url"; then
    fail "site público indisponível: $public_url"
fi

if [[ -n "$legacy_public_url" && "$legacy_public_url" != "$public_url" ]] && \
    ! curl "${curl_health_args[@]}" "$legacy_public_url"; then
    fail "legacy public site unavailable: $legacy_public_url"
fi

cd "$project_dir"
for service in postgres elasticsearch backend frontend nginx; do
    if ! docker compose ps --services --filter status=running | grep -Fxq "$service"; then
        fail "container não está em execução: $service"
    fi
done

backend_id="$(docker compose ps -q backend 2>/dev/null || true)"
if [[ -n "$backend_id" ]]; then
    backend_health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}' "$backend_id" 2>/dev/null || true)"
    if [[ "$backend_health" != "healthy" ]]; then
        fail "backend sem estado saudável: ${backend_health:-indisponível}"
    fi
fi

disk_percent="$(df -P / | awk 'NR == 2 {gsub(/%/, "", $5); print $5}')"
if [[ ! "$disk_percent" =~ ^[0-9]+$ ]]; then
    fail "não foi possível medir o uso do disco"
elif (( disk_percent >= disk_limit )); then
    fail "disco em ${disk_percent}% (limite ${disk_limit}%)"
fi

latest_backup="$(find "$backup_dir" -maxdepth 1 -type f -name 'vera-fidei-*.dump' -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n 1 | cut -d' ' -f2- || true)"
if [[ -z "$latest_backup" ]]; then
    fail "nenhum backup PostgreSQL encontrado"
else
    now_epoch="$(date +%s)"
    backup_epoch="$(stat -c %Y "$latest_backup" 2>/dev/null || printf '0')"
    backup_age_hours="$(( (now_epoch - backup_epoch) / 3600 ))"
    if (( backup_age_hours > backup_max_age_hours )); then
        fail "último backup tem ${backup_age_hours}h (limite ${backup_max_age_hours}h)"
    fi
    checksum_file="${latest_backup}.sha256"
    if [[ ! -s "$checksum_file" ]] || ! (cd "$backup_dir" && sha256sum --check --status "$(basename "$checksum_file")"); then
        fail "checksum do último backup inválido ou ausente"
    fi
fi

if [[ ! -s "$offsite_marker" ]]; then
    fail "nenhum backup externo criptografado confirmado"
else
    now_epoch="$(date +%s)"
    offsite_epoch="$(stat -c %Y "$offsite_marker" 2>/dev/null || printf '0')"
    offsite_age_hours="$(( (now_epoch - offsite_epoch) / 3600 ))"
    if (( offsite_age_hours > offsite_max_age_hours )); then
        fail "último backup externo tem ${offsite_age_hours}h (limite ${offsite_max_age_hours}h)"
    fi
fi

billing_reconcile_result="$(systemctl show "$billing_reconcile_unit" --property=Result --value 2>/dev/null || true)"
if [[ "$billing_reconcile_result" != "success" ]]; then
    fail "reconciliacao automatica de assinaturas falhou: ${billing_reconcile_result:-unidade indisponivel}"
fi

if ((${#failures[@]} > 0)); then
    message="$(IFS='; '; printf '%s' "${failures[*]}")"
    printf 'FAIL %s %s\n' "$(date --iso-8601=seconds)" "$message" >&2
    if [[ "$previous_status" != "fail" ]]; then
        send_email "[Vera.Fidei] Alerta de produção" "$message"
    fi
    printf 'fail\n' > "$status_file"
    exit 1
fi

printf 'OK %s site, containers, disco, backups local/externo e reconciliador Stripe saudáveis\n' "$(date --iso-8601=seconds)"
if [[ "$previous_status" == "fail" ]]; then
    send_email "[Vera.Fidei] Produção recuperada" "Site, containers, disco, backups local/externo e reconciliador Stripe voltaram ao estado saudável."
fi
printf 'ok\n' > "$status_file"
