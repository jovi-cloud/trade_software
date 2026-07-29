#!/usr/bin/env bash
# Archive all user state (database, market data, artifacts) to a dated zip.
# Run this before any migration that drops or rewrites a column.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${ROOT}/data"
BACKUP_DIR="${ROOT}/backups"
STAMP="$(date +%Y%m%d_%H%M%S)"
ARCHIVE="${BACKUP_DIR}/data_${STAMP}.tar.gz"

if [ ! -d "$DATA_DIR" ]; then
  echo "No data directory at ${DATA_DIR} - nothing to back up."
  exit 0
fi

mkdir -p "$BACKUP_DIR"

# Checkpoint the WAL so the copied .db file is complete.
if [ -f "${DATA_DIR}/app.db" ] && command -v sqlite3 >/dev/null 2>&1; then
  sqlite3 "${DATA_DIR}/app.db" "PRAGMA wal_checkpoint(TRUNCATE);" >/dev/null
fi

tar -czf "$ARCHIVE" -C "$ROOT" data

echo "Backup written to ${ARCHIVE}"
du -h "$ARCHIVE" | cut -f1
