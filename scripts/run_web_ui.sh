#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN=${PYTHON:-python3}
PORT=${PORT:-5001}

# Kill any existing process on the chosen port
if command -v lsof >/dev/null 2>&1; then
  PIDS=$(lsof -ti:"${PORT}" || true)
  if [ -n "${PIDS}" ]; then
    echo "Killing processes on port ${PORT}: ${PIDS}"
    kill -9 ${PIDS} || true
    sleep 1
  fi
fi
# Best-effort kill of previous dev server
pkill -f 'web_ui/app.py' >/dev/null 2>&1 || true

if [ ! -d .venv ]; then
  echo "Creating virtual environment (.venv)"
  ${PYTHON_BIN} -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip >/dev/null 2>&1 || true
echo "Installing requirements (including Flask)"
python -m pip install -r requirements.txt >/dev/null

export PYTHONPATH=src
echo "Starting Web UI on http://127.0.0.1:${PORT}"
python web_ui/app.py --port "${PORT}"
