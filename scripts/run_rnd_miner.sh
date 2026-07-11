#!/bin/bash
# Wrapper for scripts/rnd_miner.py -- weekly R&D idea mining (kanban #2855).
# Activates venv, loads env, runs the miner. Modeled on
# scripts/run_watch_digest.sh conventions.

set -euo pipefail

PROJECT_ROOT="/srv/projects/podcast"
cd "$PROJECT_ROOT"

# shellcheck source=/dev/null
source "$PROJECT_ROOT/.venv/bin/activate"

# rnd_miner.py loads .env itself via the same DB bootstrap other phase
# scripts use; no extra sourcing needed here.
python3 "$PROJECT_ROOT/scripts/rnd_miner.py" "$@"
