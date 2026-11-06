#!/bin/sh
set -eu

: "${OFFSITE_BACKUP_TARGET:?Set OFFSITE_BACKUP_TARGET, for example backup@example:/srv/santehgo}"
backup_root="${BACKUP_ROOT:-/var/backups/santehgo}"
rsync -a --chmod=F600,D700 --partial-dir=.rsync-partial \
    --include='complete-*/' --include='complete-*/*' --exclude='*' \
    "$backup_root/" "$OFFSITE_BACKUP_TARGET/"
