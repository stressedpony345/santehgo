#!/bin/sh
set -eu

: "${ERROR_ALERT_WEBHOOK_URL:?Set ERROR_ALERT_WEBHOOK_URL}"
: "${ERROR_ALERT_TOKEN:?Set ERROR_ALERT_TOKEN}"

project_dir="${SANTEHGO_PROJECT_DIR:-/opt/santehgo}"
disk_path="${MONITOR_DISK_PATH:-/var/lib/docker}"
disk_limit="${MONITOR_DISK_PERCENT:-85}"
certificate="${MONITOR_CERT_PATH:-/etc/letsencrypt/live/xn--80agf5ahnjz.xn--p1ai/fullchain.pem}"
certificate_days="${MONITOR_CERT_DAYS:-14}"
ready_url="${MONITOR_READY_URL:-https://xn--80agf5ahnjz.xn--p1ai/health/ready/}"
required_services="${MONITOR_SERVICES:-db web notifications nginx}"
issues=""

add_issue() {
    if [ -n "$issues" ]; then issues="$issues; "; fi
    issues="$issues$1"
}

case "$disk_limit:$certificate_days" in
    *[!0-9:]*|:*|*:) echo "Monitoring thresholds must be integers" >&2; exit 2 ;;
esac

disk_used="$(df -P "$disk_path" | awk 'NR==2 {gsub(/%/, "", $5); print $5}')"
if [ -z "$disk_used" ] || [ "$disk_used" -ge "$disk_limit" ]; then
    add_issue "disk usage is ${disk_used:-unknown}% (limit $disk_limit%)"
fi

if [ ! -r "$certificate" ]; then
    add_issue "TLS certificate is missing"
elif ! openssl x509 -checkend "$((certificate_days * 86400))" -noout -in "$certificate" >/dev/null 2>&1; then
    add_issue "TLS certificate expires in less than $certificate_days days"
fi

if ! curl --fail --silent --show-error --max-time 10 "$ready_url" >/dev/null; then
    add_issue "readiness endpoint is unavailable"
fi

cd "$project_dir"
for service in $required_services; do
    container_id="$(docker compose ps -q "$service")"
    if [ -z "$container_id" ]; then
        add_issue "container $service is absent"
        continue
    fi
    state="$(docker inspect --format '{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}' "$container_id")"
    case "$state" in
        running|running\ healthy) ;;
        *) add_issue "container $service state: $state" ;;
    esac
done

if [ -z "$issues" ]; then
    echo "monitor=ok disk=$disk_used%"
    exit 0
fi

payload="$(printf '%s' "$issues" | sed 's/\\/\\\\/g; s/"/\\"/g' | awk '{printf "%s\\n", $0}')"
if ! curl --fail --silent --show-error --max-time 10 \
    -H "Authorization: Bearer $ERROR_ALERT_TOKEN" \
    -H 'Content-Type: application/json' \
    --data "{\"service\":\"santehgo-host\",\"message\":\"$payload\"}" \
    "$ERROR_ALERT_WEBHOOK_URL" >/dev/null; then
    echo "Monitoring failed and alert delivery failed: $issues" >&2
    exit 2
fi

echo "Monitoring alert delivered: $issues" >&2
exit 1
