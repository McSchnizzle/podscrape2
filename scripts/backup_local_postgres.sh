#!/usr/bin/env bash
#
# Nightly logical backup of the local podcast PostgreSQL database (kanban #2669).
#
# Dumps the full database (schema + data) from the podcast-db container to the
# 1TB data drive and prunes dumps older than RETENTION_DAYS. The physical data
# directory also lives on /mnt/data1tb, so this protects against logical loss
# (bad migration, accidental delete) rather than drive loss; copy dumps offsite
# if drive-level durability is needed.
#
# Cron: daily at 04:50 PT (see pbrown crontab, PODCAST PIPELINE section).
set -euo pipefail

CONTAINER_NAME="podcast-db"
DB_USER="podcast"
DB_NAME="podcast"
BACKUP_DIR="${PODCAST_BACKUP_DIR:-/mnt/data1tb/pbrown-store/podcast-backups}"
RETENTION_DAYS=14

mkdir -p "$BACKUP_DIR"

STAMP=$(date +%Y%m%d_%H%M%S)
OUT="$BACKUP_DIR/podcast-${STAMP}.sql.gz"

if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "ERROR: container ${CONTAINER_NAME} is not running; no backup taken" >&2
    exit 1
fi

docker exec "$CONTAINER_NAME" pg_dump -U "$DB_USER" -d "$DB_NAME" --clean --if-exists | gzip > "$OUT"

# A dump of the live DB should never be trivially small; guard against silent truncation.
SIZE=$(stat -c%s "$OUT")
if [ "$SIZE" -lt 1024 ]; then
    echo "ERROR: backup ${OUT} is suspiciously small (${SIZE} bytes)" >&2
    exit 1
fi

find "$BACKUP_DIR" -name 'podcast-*.sql.gz' -mtime +"$RETENTION_DAYS" -delete

echo "backup OK: ${OUT} (${SIZE} bytes); retained: $(ls "$BACKUP_DIR" | wc -l) dumps"
