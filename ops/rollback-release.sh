#!/bin/sh
set -eu

deploy_root="${1:-/opt/santehgo}"
deploy_root="$(cd "$deploy_root" && pwd -P)"
releases_root="$deploy_root/releases"
current_link="$deploy_root/current"
previous_link="$deploy_root/previous"

if [ ! -L "$current_link" ] || [ ! -L "$previous_link" ]; then
    echo "Both current and previous release links are required" >&2
    exit 1
fi
current="$(readlink -f "$current_link")"
previous="$(readlink -f "$previous_link")"
case "$current:$previous" in
    "$releases_root"/*:"$releases_root"/*) ;;
    *) echo "Release links point outside $releases_root" >&2; exit 2 ;;
esac

compose() {
    directory="$1"
    shift
    docker compose --project-name santehgo --env-file "$deploy_root/.env" \
        -f "$directory/docker-compose.yml" "$@"
}

compose "$current" --profile ops run --rm backup /scripts/backup.sh
compose "$previous" build web notifications
compose "$previous" up -d --remove-orphans
compose "$previous" exec -T web python manage.py check
compose "$previous" exec -T web python manage.py check_master_admin --check-approval
ln -sfn "$current" "$previous_link"
ln -sfn "$previous" "$current_link"
compose "$previous" ps
echo "rollback_ok=$(basename "$previous")"
