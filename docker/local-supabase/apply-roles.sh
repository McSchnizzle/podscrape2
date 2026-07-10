#!/usr/bin/env bash
# Idempotent apply of init-roles.sql against the LIVE podcast-db container.
# Safe to re-run any time (see init-roles.sql for the idempotency guards).
#
# Usage:
#   cp docker/local-supabase/.env.example docker/local-supabase/.env
#   # fill in AUTHENTICATOR_PASSWORD / JWT_SECRET / POSTGRES_DB in .env
#   docker/local-supabase/apply-roles.sh
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$DIR/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE -- copy .env.example to .env and fill in secrets first." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

: "${PODCAST_DB_CONTAINER:=podcast-db}"
: "${POSTGRES_USER:=podcast}"
: "${POSTGRES_DB:=podcast}"
: "${AUTHENTICATOR_PASSWORD:?AUTHENTICATOR_PASSWORD must be set in $ENV_FILE}"

if ! docker ps --format '{{.Names}}' | grep -qx "$PODCAST_DB_CONTAINER"; then
  echo "Container '$PODCAST_DB_CONTAINER' is not running. Start it before applying roles." >&2
  exit 1
fi

docker exec -i "$PODCAST_DB_CONTAINER" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -v ON_ERROR_STOP=1 \
  -v authpass="$AUTHENTICATOR_PASSWORD" \
  < "$DIR/init-roles.sql"

echo "Roles applied to ${PODCAST_DB_CONTAINER}/${POSTGRES_DB}."
