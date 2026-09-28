#!/bin/bash
# Standalone audio phase wrapper - called by 3-hourly cron
# Discovers new episodes on every feed, then drains pending episodes via Whisper transcription + scoring, decoupled from the
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

# Discovery first (Paul 2026-09-28): check ALL feeds, RSS and YouTube, every 3 hours instead of only
# at the 21:00 pipeline run. Before this, an episode published on the digest day could never make
# that night's digest: it was discovered at 21:00 and transcribed after the 21:05 digest. Discovery
# is idempotent (already-known episodes are skipped), so the 21:00 run finding them again is harmless.
# A discovery failure is logged and never blocks transcription of what is already pending.
echo "Discovery started: $(date)" >> "$LOG_FILE"
nice -n 10 python3 scripts/run_discovery.py --days-back 5 --limit 10 2>&1 | tee -a "$LOG_FILE" > /dev/null
DISCOVERY_EXIT=${PIPESTATUS[0]}
echo "Discovery finished (exit $DISCOVERY_EXIT) after $(( $(date +%s) - START_TIME ))s" >> "$LOG_FILE"

# The transcription time budget (run_audio.py, default 5400s of the 7200s cron timeout) must count
# the discovery minutes too, or a long discovery pushes transcription into the hard kill.
BUDGET_TOTAL=${PODCAST_AUDIO_BUDGET_SECONDS:-5400}
BUDGET_LEFT=$(( BUDGET_TOTAL - ( $(date +%s) - START_TIME ) ))
[ "$BUDGET_LEFT" -lt 600 ] && BUDGET_LEFT=600
export PODCAST_AUDIO_BUDGET_SECONDS=$BUDGET_LEFT

# Run the standalone audio phase
# --max-youtube 3 + --max-rss 3 = balanced fetch from each feed type (6 total max).
# Prevents one feed type's backlog from starving the other in 3-hourly runs.
# Share et01 politely (Paul 2026-09-27): local Whisper on torch otherwise spawns one BLAS/OpenMP
# thread per core in EVERY worker thread (~14 of 32 cores for hours, halving VitalAI CI). Cap the
# math pools and run niced so interactive work and CI get the CPU first.
export OMP_NUM_THREADS=6 MKL_NUM_THREADS=6 OPENBLAS_NUM_THREADS=6 TORCH_NUM_THREADS=6
nice -n 15 python3 scripts/run_audio.py --max-youtube 3 --max-rss 3 --verbose 2>&1 | tee -a "$LOG_FILE" > "$TEMP_LOG"
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
