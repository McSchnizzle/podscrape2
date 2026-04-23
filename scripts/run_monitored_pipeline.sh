#!/bin/bash
# Debug-only wrapper: run the full pipeline with per-phase email monitoring.
# Survives SSH disconnect when launched via nohup.
#
# Usage:
#   ssh et01 'nohup bash /srv/projects/podcast/scripts/run_monitored_pipeline.sh > /tmp/monitor.log 2>&1 &'
#
# Or run in foreground for a test:
#   ssh et01 'bash /srv/projects/podcast/scripts/run_monitored_pipeline.sh --limit 2'
#
# Not used by cron — cron uses run_pipeline_with_alerts.sh (silent-on-success wrapper).
# This is for debug/verification of the pipeline when you want live visibility.
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="/home/pbrown/logs/monitored-pipeline-$(date +%Y%m%d_%H%M%S).log"
PID_FILE="/tmp/monitored-pipeline.pid"

mkdir -p "$(dirname "$LOG_FILE")"

# Prevent double-run
if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "ERROR: another monitored pipeline is running (PID $(cat "$PID_FILE")). Aborting." | tee -a "$LOG_FILE"
    exit 1
fi

echo $$ > "$PID_FILE"
trap rm -f  EXIT

cd "$PROJECT_DIR"
set -a
source .env
set +a
. .venv/bin/activate

echo "=== Monitored pipeline started at $(date) (pid $$) ===" | tee -a "$LOG_FILE"
echo "Args: $@" | tee -a "$LOG_FILE"
echo "Log:  $LOG_FILE" | tee -a "$LOG_FILE"
echo | tee -a "$LOG_FILE"

python3 scripts/monitor_pipeline.py "$@" 2>&1 | tee -a "$LOG_FILE"
EXIT_CODE=${PIPESTATUS[0]}

echo | tee -a "$LOG_FILE"
echo "=== Monitored pipeline ended at $(date), exit=$EXIT_CODE ===" | tee -a "$LOG_FILE"
exit $EXIT_CODE
