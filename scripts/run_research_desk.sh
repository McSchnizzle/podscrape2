#!/bin/bash
# Wrapper for scripts/research_desk.py — used by et01 cron.
# Activates venv, loads env, runs the weekly research desk injector.

set -euo pipefail

PROJECT_ROOT="/srv/projects/podcast"
cd "$PROJECT_ROOT"

# shellcheck source=/dev/null
source "$PROJECT_ROOT/.venv/bin/activate"

# research_desk.py loads .env itself via python-dotenv; no extra sourcing needed
python3 "$PROJECT_ROOT/scripts/research_desk.py" "$@"
