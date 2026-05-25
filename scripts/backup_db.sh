#!/usr/bin/env sh
set -eu

BACKUP_DIR="${BACKUP_DIR:-./backups}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$BACKUP_DIR"

if [ -f ".env.production" ]; then
  set -a
  . ./.env.production
  set +a
fi

if [ "${DATABASE_URL:-}" = "" ]; then
  echo "DATABASE_URL is required." >&2
  exit 1
fi

case "$DATABASE_URL" in
  sqlite:///*)
    DB_PATH="${DATABASE_URL#sqlite:///}"
    cp "$DB_PATH" "$BACKUP_DIR/consensus_alpha_$STAMP.sqlite"
    echo "$BACKUP_DIR/consensus_alpha_$STAMP.sqlite"
    ;;
  postgresql* )
    OUT="$BACKUP_DIR/consensus_alpha_$STAMP.sql"
    docker compose -f docker-compose.prod.yml exec -T postgres \
      pg_dump -U "${POSTGRES_USER:-consensus}" "${POSTGRES_DB:-consensus_alpha}" > "$OUT"
    echo "$OUT"
    ;;
  *)
    echo "Unsupported DATABASE_URL for backup: $DATABASE_URL" >&2
    exit 1
    ;;
esac
