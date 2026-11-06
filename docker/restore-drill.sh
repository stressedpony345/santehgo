#!/bin/sh
set -eu

backup_root="${BACKUP_ROOT:-/backups}"
requested="${1:-latest}"
case "$requested" in
    latest)
        backup_dir="$(find "$backup_root" -mindepth 1 -maxdepth 1 -type d -name 'complete-*' -print | sort -r | head -n 1)"
        ;;
    complete-*) backup_dir="$backup_root/$requested" ;;
    *) echo "Use 'latest' or an exact complete-* backup id" >&2; exit 2 ;;
esac

if [ -z "$backup_dir" ] || [ ! -f "$backup_dir/COMPLETE" ]; then
    echo "A complete backup was not found" >&2
    exit 1
fi

drill_db="santehgo_restore_$$_$(date -u +%H%M%S)"
restore_dir="/tmp/$drill_db-media"
cleanup() {
    dropdb --if-exists "$drill_db" >/dev/null 2>&1 || true
    rm -rf "$restore_dir"
}
trap cleanup EXIT HUP INT TERM

(
    cd "$backup_dir"
    sha256sum -c SHA256SUMS
)
pg_restore --list "$backup_dir/database.dump" >/dev/null
tar -tzf "$backup_dir/media.tar.gz" > "/tmp/$drill_db-tar-list"
if grep -Eq '(^/|(^|/)\.\.(/|$))' "/tmp/$drill_db-tar-list"; then
    echo "Unsafe media archive paths" >&2
    exit 1
fi
rm -f "/tmp/$drill_db-tar-list"

createdb "$drill_db"
pg_restore --exit-on-error --no-owner --no-acl --dbname="$drill_db" "$backup_dir/database.dump"
mkdir -p "$restore_dir"
tar -xzf "$backup_dir/media.tar.gz" -C "$restore_dir"

migration_count="$(psql -At --dbname="$drill_db" -c 'SELECT count(*) FROM django_migrations')"
if [ "$migration_count" -lt 1 ]; then
    echo "Restored database has no Django migrations" >&2
    exit 1
fi

media_paths="/tmp/$drill_db-media-paths"
psql -At --dbname="$drill_db" -c "
    SELECT image FROM core_subcategory WHERE image <> ''
    UNION ALL SELECT completion_photo FROM core_servicerequest WHERE completion_photo <> ''
    UNION ALL SELECT file FROM core_completionmedia WHERE file <> ''
" > "$media_paths"
missing=0
while IFS= read -r relative_path; do
    if [ ! -f "$restore_dir/$relative_path" ]; then
        echo "Missing restored media: $relative_path" >&2
        missing=1
    fi
done < "$media_paths"
rm -f "$media_paths"
if [ "$missing" -ne 0 ]; then
    exit 1
fi

request_count="$(psql -At --dbname="$drill_db" -c 'SELECT count(*) FROM core_servicerequest')"
echo "restore_drill=ok backup=$(basename "$backup_dir") migrations=$migration_count requests=$request_count"
