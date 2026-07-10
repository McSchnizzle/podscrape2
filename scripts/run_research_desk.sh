#!/bin/bash
# Wrapper for scripts/research_desk.py — used by et01 cron.
# Activates venv, loads env, runs the weekly research desk injector.
#
# Locking: the patrol cron-wrapper already flocks scheduled runs by job
# name, but this script can also be invoked directly/manually. The ledger
# is atomically written per-entry but is still a read-modify-write across
# a run, so two concurrent runs racing on it could interleave lost updates.
# Take our own lock here too, and exit cleanly (not an error) if held.

set -euo pipefail

PROJECT_ROOT="/srv/projects/podcast"
cd "$PROJECT_ROOT"

LOCK_FILE="$PROJECT_ROOT/data/.research_desk.lock"
mkdir -p "$PROJECT_ROOT/data"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    echo "run_research_desk: another run already holds $LOCK_FILE, exiting" >&2
    exit 0
fi

# shellcheck source=/dev/null
source "$PROJECT_ROOT/.venv/bin/activate"

# research_desk.py loads .env itself via python-dotenv; no extra sourcing needed
python3 "$PROJECT_ROOT/scripts/research_desk.py" "$@"
