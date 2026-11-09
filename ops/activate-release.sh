#!/bin/sh
set -eu

deploy_root="${1:?deploy root is required}"
release_dir="${2:?release directory is required}"
releases_root="$deploy_root/releases"
current_link="$deploy_root/current"
previous_link="$deploy_root/previous"

deploy_root="$(cd "$deploy_root" && pwd -P)"
release_dir="$(cd "$release_dir" && pwd -P)"
case "$release_dir" in
    "$deploy_root"/releases/*) ;;
    *) echo "Release must be inside $deploy_root/releases" >&2; exit 2 ;;
esac
if [ ! -f "$deploy_root/.env" ] || [ ! -f "$release_dir/docker-compose.yml" ]; then
    echo "Deployment .env or release compose file is missing" >&2
    exit 2
fi
ln -sfn "$deploy_root/.env" "$release_dir/.env"

compose() {
    directory="$1"
    shift
    docker compose --project-name santehgo --env-file "$deploy_root/.env" \
        -f "$directory/docker-compose.yml" "$@"
}

old_release=""
if [ -L "$current_link" ]; then
    old_release="$(readlink -f "$current_link")"
    case "$old_release" in "$releases_root"/*) ;; *) old_release="" ;; esac
fi

backup_source="$release_dir"
if [ -n "$old_release" ]; then backup_source="$old_release"; fi
compose "$release_dir" build backup
compose "$backup_source" --profile ops run --rm backup /scripts/backup.sh
compose "$release_dir" build web notifications

rollback_on_error() {
    status=$?
    if [ "$status" -ne 0 ] && [ -n "$old_release" ]; then
        echo "Activation failed; restoring previous application containers" >&2
        compose "$old_release" up -d --remove-orphans || true
    fi
    exit "$status"
}
trap rollback_on_error EXIT HUP INT TERM

compose "$release_dir" up -d --remove-orphans
compose "$release_dir" exec -T web python manage.py check
compose "$release_dir" exec -T web python manage.py check_master_admin --check-approval
ready_url="${RELEASE_READY_URL:-https://xn--80agf5ahnjz.xn--p1ai/health/ready/}"
python3 - "$ready_url" <<'PY'
import sys
import time
import urllib.request

request = urllib.request.Request(sys.argv[1], headers={'Cache-Control': 'no-cache'})
for attempt in range(6):
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status == 200:
                break
    except Exception:
        pass
    if attempt == 5:
        sys.exit('Production readiness check failed after six attempts')
    time.sleep(3)
PY

if [ -n "$old_release" ]; then
    ln -sfn "$old_release" "$previous_link"
fi
ln -sfn "$release_dir" "$current_link"
trap - EXIT HUP INT TERM

kept=0
for directory in $(find "$releases_root" -mindepth 1 -maxdepth 1 -type d -print | sort -r); do
    if [ "$directory" = "$release_dir" ] || [ "$directory" = "$old_release" ]; then continue; fi
    kept=$((kept + 1))
    if [ "$kept" -gt 3 ]; then rm -rf "$directory"; fi
done

compose "$release_dir" ps
echo "release_activated=$(basename "$release_dir")"
