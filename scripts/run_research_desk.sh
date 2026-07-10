#!/bin/bash
# Wrapper for scripts/research_desk.py — used by et01 cron.
# Activates venv, loads env, runs the weekly research desk injector.
#
# Locking: research_desk.py's main() takes its own non-blocking flock on
# data/.research_desk.lock around the whole run, covering this wrapper AND
# any direct `python3 scripts/research_desk.py` invocation from one choke
# point. Deliberately NOT duplicated here -- flock is per open-file-
# description, so a second independent lock attempt on the SAME path from
# this wrapper would self-conflict with the child python3 process's own
# lock attempt (blocks/fails against its own parent rather than recognizing
# common ownership), turning every wrapper-invoked run into a false
# "another run holds the lock" no-op.

set -euo pipefail

PROJECT_ROOT="/srv/projects/podcast"
cd "$PROJECT_ROOT"

# shellcheck source=/dev/null
source "$PROJECT_ROOT/.venv/bin/activate"

# research_desk.py loads .env itself via python-dotenv; no extra sourcing needed
python3 "$PROJECT_ROOT/scripts/research_desk.py" "$@"
