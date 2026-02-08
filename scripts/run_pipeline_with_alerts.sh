#!/bin/bash
# Pipeline wrapper with failure alerting
# Called by cron - sends email on failure
#
# Usage: ./scripts/run_pipeline_with_alerts.sh
# Requires: GMAIL_APP_PASSWORD in .env

set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="/home/pbrown/logs/podcast-cron.log"
TEMP_LOG=$(mktemp)
START_TIME=$(date +%s)

cd "$PROJECT_DIR"

# Load environment
set -a
source .env
set +a

# Activate venv
. .venv/bin/activate

echo "========================================" >> "$LOG_FILE"
echo "Pipeline started: $(date)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

# Run the pipeline, capturing output to both the main log and temp log
python3 run_full_pipeline_orchestrator.py --verbose --days-back 5 --limit 10 2>&1 | tee -a "$LOG_FILE" > "$TEMP_LOG"
EXIT_CODE=${PIPESTATUS[0]}

END_TIME=$(date +%s)
RUNTIME="$((END_TIME - START_TIME)) seconds"

if [ $EXIT_CODE -ne 0 ]; then
    echo "Pipeline FAILED with exit code $EXIT_CODE after $RUNTIME" >> "$LOG_FILE"

    # Send failure notification
    LOG_TAIL=$(tail -50 "$TEMP_LOG")
    python3 "$SCRIPT_DIR/notify_failure.py" "$EXIT_CODE" "$LOG_TAIL" 2>&1 || true
else
    echo "Pipeline completed successfully in $RUNTIME" >> "$LOG_FILE"
fi

rm -f "$TEMP_LOG"
exit $EXIT_CODE
