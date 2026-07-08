#!/usr/bin/env bash
#
# Setup local PostgreSQL for the podcast pipeline (et01).
#
# This script creates a Docker container running PostgreSQL 16, creates the
# database user and database, runs all Alembic migrations, and prints the
# DATABASE_URL to use in .env or export.
#
# Usage:
#   bash scripts/setup_local_postgres.sh           # create + migrate
#   bash scripts/setup_local_postgres.sh --reset   # drop + recreate
#
set -euo pipefail

CONTAINER_NAME="podcast-db"
DB_USER="podcast"
DB_NAME="podcast"
DB_PASSWORD="podcast_local_dev"
DB_PORT="5470"
DB_HOST="127.0.0.1"
# Data directory lives on the 1TB data drive (kanban #2669 AC1), not the root fs.
DB_DATA_DIR="${PODCAST_DB_DATA_DIR:-/mnt/data1tb/pbrown-store/podcast-db-data}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Activate venv if present
if [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
fi

if [ "${1:-}" = "--reset" ]; then
    echo "🗑  Removing existing container..."
    docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
    if [ -d "$DB_DATA_DIR" ] && [ -n "$(ls -A "$DB_DATA_DIR" 2>/dev/null)" ]; then
        echo "⚠️  Data dir $DB_DATA_DIR is kept; the recreated container reuses the existing"
        echo "    PGDATA (POSTGRES_* init env is ignored). Use --reset-data to wipe it too."
    fi
elif [ "${1:-}" = "--reset-data" ]; then
    echo "🗑  Removing existing container AND data dir $DB_DATA_DIR..."
    docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
    read -r -p "Really delete all data in $DB_DATA_DIR? [y/N] " CONFIRM
    if [ "$CONFIRM" = "y" ] || [ "$CONFIRM" = "Y" ]; then
        rm -rf "$DB_DATA_DIR"
    else
        echo "Aborted; data dir kept."
        exit 1
    fi
fi

# Check if container already exists
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "✓ Container '$CONTAINER_NAME' is already running."
    else
        echo "▶ Starting existing container '$CONTAINER_NAME'..."
        docker start "$CONTAINER_NAME"
        sleep 2
    fi
else
    echo "🚀 Creating PostgreSQL 16 container '$CONTAINER_NAME'..."
    mkdir -p "$DB_DATA_DIR"
    docker run -d \
        --name "$CONTAINER_NAME" \
        -e POSTGRES_USER="$DB_USER" \
        -e POSTGRES_PASSWORD="$DB_PASSWORD" \
        -e POSTGRES_DB="$DB_NAME" \
        -p "${DB_HOST}:${DB_PORT}:5432" \
        -v "${DB_DATA_DIR}:/var/lib/postgresql/data" \
        --restart unless-stopped \
        postgres:16
    sleep 3
fi

# Wait for Postgres to be ready
echo "⏳ Waiting for PostgreSQL to accept connections..."
for i in $(seq 1 15); do
    if docker exec "$CONTAINER_NAME" pg_isready -U "$DB_USER" > /dev/null 2>&1; then
        echo "✓ PostgreSQL is ready."
        break
    fi
    sleep 1
    if [ "$i" = "15" ]; then
        echo "❌ PostgreSQL did not become ready in time."
        exit 1
    fi
done

DATABASE_URL="postgresql+psycopg://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"

echo ""
echo "📋 Running Alembic migrations..."
DATABASE_URL="$DATABASE_URL" python3 -m alembic upgrade head

echo ""
echo "✅ Local PostgreSQL database is ready."
echo ""
echo "   DATABASE_URL=$DATABASE_URL"
echo ""
echo "   Add this line to your .env or export it before running the pipeline."
