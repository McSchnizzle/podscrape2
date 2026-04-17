#!/bin/bash
# Wrapper for scripts/run_watch_digest.py — used by et01 cron.
# Activates venv, loads env, runs digest.

set -euo pipefail

PROJECT_ROOT="/srv/projects/podcast-pipeline"
cd "$PROJECT_ROOT"

# shellcheck source=/dev/null
source "$PROJECT_ROOT/.venv/bin/activate"

# run_watch_digest.py loads .env itself via python-dotenv; no extra sourcing needed
python3 "$PROJECT_ROOT/scripts/run_watch_digest.py" "$@"
