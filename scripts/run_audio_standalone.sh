#!/bin/bash
# Standalone audio phase wrapper - called by 3-hourly cron
# Drains pending episodes via Whisper transcription + scoring, decoupled from the
# nightly digest pipeline so transcription latency cannot starve digest generation.
#
# Usage: ./scripts/run_audio_standalone.sh
# Cron-wrapped via patrol/cron-wrapper.sh which provides flock + timeout.

set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="/home/pbrown/logs/podcast-audio-cron.log"
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
echo "Audio phase started: $(date)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

# Run the standalone audio phase
# --max-youtube 3 + --max-rss 3 = balanced fetch from each feed type (6 total max).
# Prevents one feed type's backlog from starving the other in 3-hourly runs.
python3 scripts/run_audio.py --max-youtube 3 --max-rss 3 --verbose 2>&1 | tee -a "$LOG_FILE" > "$TEMP_LOG"
EXIT_CODE=${PIPESTATUS[0]}

END_TIME=$(date +%s)
RUNTIME="$((END_TIME - START_TIME)) seconds"

if [ $EXIT_CODE -ne 0 ]; then
    echo "Audio phase FAILED with exit code $EXIT_CODE after $RUNTIME" >> "$LOG_FILE"

    # Send failure notification
    LOG_TAIL=$(tail -50 "$TEMP_LOG")
    python3 "$SCRIPT_DIR/notify_failure.py" "$EXIT_CODE" "$LOG_TAIL" 2>&1 || true
else
    echo "Audio phase completed successfully in $RUNTIME" >> "$LOG_FILE"
fi

rm -f "$TEMP_LOG"
exit $EXIT_CODE
