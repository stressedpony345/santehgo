#!/bin/sh
set -eu

backup_root="${BACKUP_ROOT:-/backups}"
media_source="${MEDIA_SOURCE:-/source/media}"
retention_count="${BACKUP_RETENTION_COUNT:-14}"
lock_file="$backup_root/.backup.flock"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
temporary_dir="$backup_root/.partial-$timestamp-$$"
complete_dir="$backup_root/complete-$timestamp"

case "$retention_count" in
    ''|*[!0-9]*) echo "BACKUP_RETENTION_COUNT must be a positive integer" >&2; exit 2 ;;
esac
if [ "$retention_count" -lt 1 ]; then
    echo "BACKUP_RETENTION_COUNT must be at least 1" >&2
    exit 2
fi

umask 077
mkdir -p "$backup_root"
exec 9>"$lock_file"
if ! flock -n 9; then
    echo "Another backup is already running" >&2
    exit 1
fi
cleanup() {
    rm -rf "$temporary_dir"
}
trap cleanup EXIT HUP INT TERM

mkdir "$temporary_dir"
pg_dump --format=custom --no-owner --no-acl --file="$temporary_dir/database.dump"
tar -czf "$temporary_dir/media.tar.gz" -C "$media_source" .
pg_restore --list "$temporary_dir/database.dump" >/dev/null
tar -tzf "$temporary_dir/media.tar.gz" >/dev/null

database_bytes="$(wc -c < "$temporary_dir/database.dump" | tr -d ' ')"
media_bytes="$(wc -c < "$temporary_dir/media.tar.gz" | tr -d ' ')"
cat > "$temporary_dir/MANIFEST" <<EOF
created_at_utc=$timestamp
database=${PGDATABASE:-}
database_bytes=$database_bytes
media_bytes=$media_bytes
release_sha=${RELEASE_SHA:-unknown}
EOF
(
    cd "$temporary_dir"
    sha256sum database.dump media.tar.gz MANIFEST > SHA256SUMS
)
touch "$temporary_dir/COMPLETE"
chmod 600 "$temporary_dir"/*
mv "$temporary_dir" "$complete_dir"

kept=0
for directory in $(find "$backup_root" -mindepth 1 -maxdepth 1 -type d -name 'complete-*' -print | sort -r); do
    kept=$((kept + 1))
    if [ "$kept" -gt "$retention_count" ] && [ -f "$directory/COMPLETE" ]; then
        rm -rf "$directory"
    fi
done

echo "$complete_dir"
